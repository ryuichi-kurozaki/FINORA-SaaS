"""Manual payouts: invoice card payments settle to the FINORA Stripe account; FINORA transfers the net (amount − refunds − Stripe fee − transfer fee) to the client's assigned consultant."""
import asyncio
import json
import os
from datetime import date

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import audit, clean, db, decrypt, encrypt, forbid_demo, new_id, notify, now_iso, platform_admin, require_roles

router = APIRouter(prefix="/api")
FEE_RATE = float(os.environ.get("STRIPE_FEE_RATE", "0.036"))
staff = require_roles("admin", "consultant")


class BankIn(BaseModel):
    bank_name: str = Field(min_length=1, max_length=60)
    bank_code: str = Field("", pattern=r"^(\d{4})?$")
    branch_name: str = Field(min_length=1, max_length=60)
    branch_code: str = Field("", pattern=r"^(\d{3})?$")
    account_type: str = Field(pattern="^(ORDINARY|CHECKING|SAVINGS)$")
    account_number: str = Field(pattern=r"^\d{7}$")
    holder_kana: str = Field(min_length=1, max_length=60, pattern=r"^[ァ-ヶーｦ-ﾟ　 ()（）.．・A-ZＡ-Ｚ0-9０-９]+$")


class PayoutIn(BaseModel):
    transfer_fee: int = Field(0, ge=0, le=10000)
    transfer_date: str = Field(min_length=10, max_length=10)
    note: str = Field("", max_length=500)


def bank_of(u):
    raw = (u or {}).get("payout_bank") or {}
    return json.loads(decrypt(raw["enc"])) if raw.get("enc") else None


def masked(b):
    return b and {**b, "account_number": "***" + b["account_number"][-4:]}


async def card_clients(tid):
    """Client ids whose assigned consultant has registered a payout account (card payment allowed)."""
    banked = {u["id"] for u in await db.users.find({"tenant_id": tid, "payout_bank": {"$exists": True}}, {"id": 1}).to_list(1000)}
    return {c["id"] for c in await db.clients.find({"tenant_id": tid}, {"id": 1, "consultant_id": 1}).to_list(20000) if c.get("consultant_id") in banked}


async def _payee(invoice_id):
    inv = await db.invoices.find_one({"id": invoice_id}, {"client_id": 1}) or {}
    return ((await db.clients.find_one({"id": inv.get("client_id")}, {"consultant_id": 1})) or {}).get("consultant_id")


def stripe_fee_sync(pi, amount):
    try:
        bt = stripe.PaymentIntent.retrieve(pi, expand=["latest_charge.balance_transaction"]).latest_charge.balance_transaction
        return float(bt.fee), False
    except Exception:  # noqa: BLE001
        return float(round(amount * FEE_RATE)), True


async def record_fee(payment_id, pi, amount):
    fee, est = await asyncio.to_thread(stripe_fee_sync, pi, amount) if pi else (float(round(amount * FEE_RATE)), True)
    p = await db.payments.find_one({"id": payment_id}, {"invoice_id": 1})
    await db.payments.update_one({"id": payment_id}, {"$set": {"stripe_fee": fee, "stripe_fee_estimated": est, "payee_id": await _payee(p["invoice_id"])}})


def _item(p):
    fee = p.get("stripe_fee") if p.get("stripe_fee") is not None else float(round(p["amount"] * FEE_RATE))
    net = p["amount"] - (p.get("refunded_amount") or 0) - fee
    return {"payment_id": p["id"], "invoice_id": p["invoice_id"], "invoice_number": p.get("invoice_number"), "date": p.get("date"), "amount": p["amount"],
            "refunded": p.get("refunded_amount") or 0, "stripe_fee": fee, "fee_estimated": p.get("stripe_fee") is None or bool(p.get("stripe_fee_estimated")),
            "net": net, "settled": p.get("payout_settled") or 0, "pending": net - (p.get("payout_settled") or 0)}


def _sum(items):
    return {"items": items, "total": sum(i["pending"] for i in items), "gross": sum(i["amount"] for i in items if not i["settled"]),
            "fees": sum(i["stripe_fee"] for i in items if not i["settled"])}


async def pending_by_payee():
    out = {}
    for p in await db.payments.find({"source": "STRIPE"}).sort("date", 1).to_list(20000):
        i = _item(p)
        if abs(i["pending"]) >= 0.5:
            out.setdefault(p.get("payee_id") or await _payee(p["invoice_id"]), []).append(i)
    return out


@router.get("/payouts/bank")
async def get_bank(user=Depends(staff)):
    u = await db.users.find_one({"id": user["id"]}) or {}
    return {"bank": bank_of(u), "updated_at": (u.get("payout_bank") or {}).get("updated_at")}


@router.put("/payouts/bank")
async def put_bank(body: BankIn, request: Request, user=Depends(staff)):
    forbid_demo(user)
    u = await db.users.find_one({"id": user["id"]}) or {}
    b = body.model_dump()
    await db.users.update_one({"id": user["id"]}, {"$set": {"payout_bank": {"enc": encrypt(json.dumps(b, ensure_ascii=False)), "updated_at": now_iso()}}})
    await audit(user, "update", "payout_bank", user["id"], before=masked(bank_of(u)), after=masked(b), request=request, label="カード決済の受取口座")
    return {"bank": b}


@router.get("/payouts")
async def my_payouts(user=Depends(staff)):
    hist = [clean(x) for x in await db.payouts.find({"payee_id": user["id"]}).sort("created_at", -1).to_list(200)]
    return {"pending": _sum((await pending_by_payee()).get(user["id"], [])), "history": hist}


@router.get("/platform/payouts")
async def platform_payouts(user=Depends(platform_admin)):
    rows = []
    for uid, items in (await pending_by_payee()).items():
        u = await db.users.find_one({"id": uid}) or {}
        t = await db.tenants.find_one({"id": u.get("tenant_id")}, {"name": 1}) or {}
        rows.append({"payee_id": uid, "payee_name": u.get("name") or "—", "payee_email": u.get("email"), "tenant_name": t.get("name"), "bank": bank_of(u), **_sum(items)})
    hist = [clean(x) for x in await db.payouts.find({}).sort("created_at", -1).to_list(500)]
    return {"payees": sorted(rows, key=lambda r: -r["total"]), "history": hist}


@router.post("/platform/payouts/{uid}")
async def mark_sent(uid: str, body: PayoutIn, request: Request, user=Depends(platform_admin)):
    date.fromisoformat(body.transfer_date)
    u = await db.users.find_one({"id": uid})
    bank = bank_of(u)
    if not bank:
        raise HTTPException(409, "受取口座が未登録です (No payout bank account registered)")
    p = _sum((await pending_by_payee()).get(uid, []))
    amount = p["total"] - body.transfer_fee
    if amount <= 0:
        raise HTTPException(409, "送金できる金額がありません (Nothing to transfer)")
    t = await db.tenants.find_one({"id": u.get("tenant_id")}, {"name": 1}) or {}
    doc = {"id": new_id(), "payee_id": uid, "payee_name": u.get("name"), "tenant_id": u.get("tenant_id"), "tenant_name": t.get("name"), "items": p["items"],
           "total": p["total"], "transfer_fee": body.transfer_fee, "amount": amount, "transfer_date": body.transfer_date, "note": body.note,
           "bank": masked(bank), "status": "SENT", "created_at": now_iso(), "created_by": user["id"], "created_by_name": user.get("name")}
    await db.payouts.insert_one(doc)
    for i in p["items"]:
        await db.payments.update_one({"id": i["payment_id"]}, {"$set": {"payout_settled": i["net"], "payee_id": uid}, "$push": {"payout_ids": doc["id"]}})
    await audit(user, "payout", "payouts", doc["id"], after={"payee_id": uid, "amount": amount, "transfer_fee": body.transfer_fee, "items": len(p["items"])},
                request=request, label=f"{u.get('name')} ¥{amount:,.0f}")
    await notify(u.get("tenant_id"), [uid], "payout_sent", {"label": f"¥{amount:,.0f} ({body.transfer_date})", "amount": amount}, None, "/settings", user)
    return clean(doc)
