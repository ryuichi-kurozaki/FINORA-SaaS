"""Consulting contracts -> invoices -> payments (consultant <-> customer). Kept separate from FINORA SaaS billing (tenancy.py)."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from payouts import card_clients
from invoice_notify import send_invoice_issued
from core import (forbid_demo, db, new_id, now_iso, clean, current, staff, admin_only, scope, audit, accessible_ids,
                  notify, client_user_ids, consultant_ids)

router = APIRouter(prefix="/api")
OPEN = ("ISSUED", "PARTIALLY_PAID", "OVERDUE")
METHODS = ("BANK_TRANSFER", "CREDIT_CARD", "CASH", "OTHER")


def today():
    return datetime.now().date().isoformat()


def totals(items, rate, mode):
    gross = round(sum((i.get("quantity") or 0) * (i.get("unit_price") or 0) for i in items))
    r = (rate or 0) / 100
    if mode == "exempt":
        return gross, 0, gross
    if mode == "inclusive":
        tax = round(gross - gross / (1 + r))
        return gross - tax, tax, gross
    tax = round(gross * r)
    return gross, tax, gross + tax


async def names(tenant_id):
    return {c["id"]: c.get("corporate_name") or c.get("name") for c in await db.clients.find({"tenant_id": tenant_id}, {"id": 1, "name": 1, "corporate_name": 1}).to_list(5000)}


async def mark_overdue(user, invs):
    for i in invs:
        if i["status"] in ("ISSUED", "PARTIALLY_PAID") and i.get("due_date") and i["due_date"] < today():
            old = i["status"]
            await db.invoices.update_one({"id": i["id"]}, {"$set": {"status": "OVERDUE"}})
            i["status"] = "OVERDUE"
            ids = await client_user_ids(i["tenant_id"], i["client_id"]) + await consultant_ids(i["tenant_id"], i["client_id"])
            await notify(i["tenant_id"], ids, "invoice_overdue", {"label": i["number"]}, i["client_id"], "/billing")
            await audit(user, "overdue", "invoices", i["id"], before={"status": old}, after={"status": "OVERDUE"}, client_id=i["client_id"], label=i["number"])
    return invs


async def next_number(tenant_id):
    ym = datetime.now().strftime("%Y%m")
    c = await db.counters.find_one_and_update({"tenant_id": tenant_id, "key": f"invoice-{ym}"}, {"$inc": {"seq": 1}},
                                              upsert=True, return_document=ReturnDocument.AFTER)
    return f"INV-{ym}-{c['seq']:04d}"


async def get_invoice(user, iid):
    inv = await db.invoices.find_one({"id": iid, "tenant_id": user["tenant_id"]})
    if not inv:
        raise HTTPException(404, "Not found")
    await scope(user, inv["client_id"])
    if user["role"] == "client" and inv["status"] == "DRAFT":
        raise HTTPException(404, "Not found")
    return inv


async def recompute(iid):
    inv = await db.invoices.find_one({"id": iid})
    pays = await db.payments.find({"invoice_id": iid}).to_list(1000)
    paid = sum(p["amount"] - (p["amount"] if p.get("refunded") else p.get("refunded_amount") or 0) for p in pays)
    st = inv["status"]
    if st not in ("DRAFT", "CANCELLED"):
        st = "PAID" if paid >= inv["total"] - 0.5 and inv["total"] > 0 else "PARTIALLY_PAID" if paid > 0 else "ISSUED"
        if st != "PAID" and inv.get("due_date") and inv["due_date"] < today():
            st = "OVERDUE"
    await db.invoices.update_one({"id": iid}, {"$set": {"paid": paid, "balance": inv["total"] - paid, "status": st, "updated_at": now_iso()}})
    return await db.invoices.find_one({"id": iid})


class Item(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: float = 1
    unit_price: float = 0


class InvoiceIn(BaseModel):
    client_id: str
    contract_id: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    items: List[Item] = []
    tax_rate: Optional[float] = None
    tax_mode: Optional[str] = None
    notes: str = Field("", max_length=2000)


async def build_invoice(user, body: InvoiceIn, period=None):
    await scope(user, body.client_id)
    con = None
    if body.contract_id:
        con = await db.contracts.find_one({"id": body.contract_id, "tenant_id": user["tenant_id"], "client_id": body.client_id})
        if not con:
            raise HTTPException(404, "Contract not found")
    items = [i.model_dump() for i in body.items] or ([{"description": con.get("service_name") or con.get("name"), "quantity": 1, "unit_price": con.get("fee") or 0}] if con else [])
    if not items:
        raise HTTPException(422, "At least one item is required")
    rate = body.tax_rate if body.tax_rate is not None else (con or {}).get("tax_rate", 10)
    mode = body.tax_mode or (con or {}).get("tax_mode") or "exclusive"
    sub, tax, total = totals(items, rate, mode)
    issue = body.issue_date or today()
    due = body.due_date or (datetime.fromisoformat(issue) + timedelta(days=int((con or {}).get("payment_terms_days") or 30))).date().isoformat()
    return {"id": new_id(), "tenant_id": user["tenant_id"], "number": await next_number(user["tenant_id"]), "client_id": body.client_id,
            "contract_id": body.contract_id, "contract_name": (con or {}).get("name"), "period": period, "issue_date": issue, "due_date": due,
            "items": items, "tax_rate": rate, "tax_mode": mode, "subtotal": sub, "tax": tax, "total": total, "paid": 0, "balance": total,
            "status": "DRAFT", "notes": body.notes, "created_by": user["id"], "created_at": now_iso(), "updated_at": now_iso()}


@router.get("/invoices")
async def list_invoices(client_id: Optional[str] = None, status: Optional[str] = None, user=Depends(current)):
    q = await scope(user, client_id)
    if user["role"] == "client":
        q["status"] = {"$ne": "DRAFT"}
    invs = await mark_overdue(user, await db.invoices.find(q).sort("issue_date", -1).to_list(5000))
    nm = await names(user["tenant_id"])
    refundable = set(await db.payments.distinct("invoice_id", {"tenant_id": user["tenant_id"], "source": "STRIPE", "refunded": {"$ne": True}})) \
        if user["role"] == "admin" else set()
    card = await card_clients(user["tenant_id"])
    out = [clean(i) | {"client_name": nm.get(i["client_id"]), "card_refundable": i["id"] in refundable, "card_enabled": i["client_id"] in card} for i in invs]
    return [i for i in out if not status or i["status"] == status]


@router.get("/invoices/{iid}")
async def invoice_detail(iid: str, user=Depends(current)):
    inv = (await mark_overdue(user, [await get_invoice(user, iid)]))[0]
    t = await db.tenants.find_one({"id": user["tenant_id"]}) or {}
    c = await db.clients.find_one({"id": inv["client_id"]}, {"name": 1, "corporate_name": 1, "email": 1})
    pays = await db.payments.find({"invoice_id": iid}).sort("date", 1).to_list(500)
    return clean(inv) | {"client_name": (c or {}).get("corporate_name") or (c or {}).get("name"), "issuer": t.get("billing_profile") or {"company_name": t.get("name")},
                         "payments": [clean(p) for p in pays]}


@router.post("/invoices")
async def create_invoice(body: InvoiceIn, request: Request, user=Depends(admin_only)):
    doc = await build_invoice(user, body)
    await db.invoices.insert_one(doc)
    await audit(user, "create", "invoices", doc["id"], after=clean(dict(doc)), request=request, label=doc["number"])
    return clean(doc)


@router.put("/invoices/{iid}")
async def update_invoice(iid: str, body: InvoiceIn, request: Request, user=Depends(admin_only)):
    inv = await get_invoice(user, iid)
    if inv["status"] != "DRAFT":
        raise HTTPException(409, "Only draft invoices can be edited")
    items = [i.model_dump() for i in body.items] or inv["items"]
    rate = body.tax_rate if body.tax_rate is not None else inv["tax_rate"]
    mode = body.tax_mode or inv["tax_mode"]
    sub, tax, total = totals(items, rate, mode)
    upd = {"items": items, "tax_rate": rate, "tax_mode": mode, "subtotal": sub, "tax": tax, "total": total, "balance": total,
           "issue_date": body.issue_date or inv["issue_date"], "due_date": body.due_date or inv["due_date"], "notes": body.notes, "updated_at": now_iso()}
    await db.invoices.update_one({"id": iid}, {"$set": upd})
    await audit(user, "update", "invoices", iid, before=clean(dict(inv)), after=upd, request=request, client_id=inv["client_id"], label=inv["number"])
    return clean(await db.invoices.find_one({"id": iid}))


@router.post("/invoices/{iid}/issue")
async def issue_invoice(iid: str, request: Request, user=Depends(admin_only)):
    inv = await get_invoice(user, iid)
    if inv["status"] != "DRAFT":
        raise HTTPException(409, "Only draft invoices can be issued")
    await db.invoices.update_one({"id": iid}, {"$set": {"status": "ISSUED", "issued_at": now_iso()}})
    await audit(user, "issue", "invoices", iid, before={"status": "DRAFT"}, after={"status": "ISSUED"}, request=request, client_id=inv["client_id"], label=inv["number"])
    await notify(user["tenant_id"], await client_user_ids(user["tenant_id"], inv["client_id"]), "invoice_issued",
                 {"label": inv["number"], "amount": inv["total"], "due": inv["due_date"]}, inv["client_id"], "/billing", user)
    d = await send_invoice_issued(inv, user["tenant_id"]) | {"at": now_iso()}
    await db.invoices.update_one({"id": iid}, {"$set": {"issue_delivery": d}})
    return clean(await recompute(iid))


@router.post("/invoices/{iid}/cancel")
async def cancel_invoice(iid: str, request: Request, user=Depends(admin_only)):
    inv = await get_invoice(user, iid)
    if inv["status"] == "PAID" or inv.get("paid"):
        raise HTTPException(409, "Invoices with payments cannot be cancelled")
    await db.invoices.update_one({"id": iid}, {"$set": {"status": "CANCELLED"}})
    await audit(user, "cancel", "invoices", iid, before={"status": inv["status"]}, after={"status": "CANCELLED"}, request=request, client_id=inv["client_id"], label=inv["number"])
    return {"ok": True}


@router.post("/invoices/generate-recurring")
async def generate_recurring(request: Request, user=Depends(admin_only)):
    t, created = today(), 0
    for con in await db.contracts.find({"tenant_id": user["tenant_id"], "status": "ACTIVE", "fee_type": {"$in": ["MONTHLY", "YEARLY"]}}).to_list(5000):
        if (con.get("start_date") or "") > t or (con.get("end_date") and con["end_date"] < t):
            continue
        period = t[:7] if con["fee_type"] == "MONTHLY" else t[:4]
        if await db.invoices.find_one({"contract_id": con["id"], "period": period, "status": {"$ne": "CANCELLED"}}):
            continue
        doc = await build_invoice(user, InvoiceIn(client_id=con["client_id"], contract_id=con["id"]), period)
        await db.invoices.insert_one(doc)
        await audit(user, "create", "invoices", doc["id"], after=clean(dict(doc)), request=request, label=doc["number"])
        created += 1
    return {"created": created}


class PaymentIn(BaseModel):
    invoice_id: str
    date: str
    amount: float = Field(gt=0)
    method: str = "BANK_TRANSFER"
    reference: str = Field("", max_length=120)
    notes: str = Field("", max_length=1000)


@router.get("/payments")
async def list_payments(client_id: Optional[str] = None, invoice_id: Optional[str] = None, user=Depends(current)):
    q = await scope(user, client_id)
    if invoice_id:
        q["invoice_id"] = invoice_id
    nm = await names(user["tenant_id"])
    return [clean(p) | {"client_name": nm.get(p["client_id"])} for p in await db.payments.find(q).sort("date", -1).to_list(5000)]


@router.post("/payments")
async def add_payment(body: PaymentIn, request: Request, user=Depends(admin_only)):
    inv = await get_invoice(user, body.invoice_id)
    if inv["status"] in ("DRAFT", "CANCELLED"):
        raise HTTPException(409, "Payments can only be recorded for issued invoices")
    if body.method not in METHODS:
        raise HTTPException(422, "Invalid payment method")
    if body.amount > inv["balance"] + 0.5:
        raise HTTPException(422, "Amount exceeds outstanding balance")
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], "client_id": inv["client_id"], "invoice_id": inv["id"], "invoice_number": inv["number"],
           **body.model_dump(), "created_by": user["id"], "created_by_name": user.get("name"), "created_at": now_iso()}
    await db.payments.insert_one(doc)
    after = await recompute(inv["id"])
    await audit(user, "create", "payments", doc["id"], after=clean(dict(doc)), request=request, label=f"{inv['number']} ¥{body.amount:,.0f}")
    await notify(user["tenant_id"], await client_user_ids(user["tenant_id"], inv["client_id"]), "payment_confirmed",
                 {"label": inv["number"], "amount": body.amount}, inv["client_id"], "/billing", user)
    return clean(after)


@router.delete("/payments/{pid}")
async def delete_payment(pid: str, request: Request, user=Depends(admin_only)):
    p = await db.payments.find_one({"id": pid, "tenant_id": user["tenant_id"]})
    if not p:
        raise HTTPException(404, "Not found")
    await scope(user, p["client_id"])
    await db.payments.delete_one({"id": pid})
    await recompute(p["invoice_id"])
    await audit(user, "delete", "payments", pid, before=clean(dict(p)), request=request, label=p.get("invoice_number"))
    return {"ok": True}


PROFILE_FIELDS = ("company_name", "representative", "address", "phone", "email", "registration_no", "bank_info", "invoice_note")


@router.get("/billing/profile")
async def get_profile(user=Depends(staff)):
    t = await db.tenants.find_one({"id": user["tenant_id"]}) or {}
    return t.get("billing_profile") or {"company_name": t.get("name")}


@router.put("/billing/profile")
async def put_profile(body: dict, request: Request, user=Depends(admin_only)):
    forbid_demo(user)
    prof = {k: str(body.get(k, ""))[:500] for k in PROFILE_FIELDS}
    t = await db.tenants.find_one({"id": user["tenant_id"]}) or {}
    await db.tenants.update_one({"id": user["tenant_id"]}, {"$set": {"billing_profile": prof}})
    await audit(user, "update", "tenants", user["tenant_id"], before=t.get("billing_profile"), after=prof, request=request)
    return prof


async def billing_summary(user):
    q = await scope(user, None)
    invs = await mark_overdue(user, await db.invoices.find({**q, "status": {"$nin": ["DRAFT", "CANCELLED"]}}).to_list(10000))
    pays = await db.payments.find(q).to_list(20000)
    nm = await names(user["tenant_id"])
    t = today()
    m, y = t[:7], t[:4]
    open_ = [i for i in invs if i["status"] in OPEN]
    over = [i for i in invs if i["status"] == "OVERDUE"]
    months = sorted({(datetime.now().replace(day=1) - timedelta(days=30 * k)).strftime("%Y-%m") for k in range(12)})
    by_client, by_contract = {}, {}
    for i in invs:
        if i["issue_date"].startswith(y):
            by_client[nm.get(i["client_id"], "—")] = by_client.get(nm.get(i["client_id"], "—"), 0) + i["total"]
            k = i.get("contract_name") or "—"
            by_contract[k] = by_contract.get(k, 0) + i["total"]
    srt = lambda d: sorted([{"key": k, "value": v} for k, v in d.items()], key=lambda x: -x["value"])  # noqa: E731
    return {
        "billed_month": sum(i["total"] for i in invs if i["issue_date"].startswith(m)),
        "paid_month": sum(p["amount"] for p in pays if p["date"].startswith(m)),
        "billed_year": sum(i["total"] for i in invs if i["issue_date"].startswith(y)),
        "paid_year": sum(p["amount"] for p in pays if p["date"].startswith(y)),
        "outstanding": sum(i["balance"] for i in open_), "outstanding_count": len(open_),
        "overdue": sum(i["balance"] for i in over), "overdue_count": len(over),
        "by_client": srt(by_client), "by_contract": srt(by_contract),
        "monthly": [{"date": mo, "billed": sum(i["total"] for i in invs if i["issue_date"].startswith(mo)),
                     "paid": sum(p["amount"] for p in pays if p["date"].startswith(mo))} for mo in months],
    }


@router.get("/billing/summary")
async def get_summary(user=Depends(staff)):
    return await billing_summary(user)


@router.get("/consultant/overview")
async def consultant_overview(user=Depends(staff)):
    t = today()
    m = t[:7]
    ids = await accessible_ids(user)
    cq = {"tenant_id": user["tenant_id"], **({"id": {"$in": ids}} if ids is not None else {})}
    q = await scope(user, None)
    clients = await db.clients.find(cq, {"id": 1, "created_at": 1}).to_list(5000)
    active = await db.contracts.distinct("client_id", {**q, "status": "ACTIVE"})
    meetings = await db.consulting.count_documents({**q, "kind": "meeting", "date": {"$regex": f"^{m}"}}) + \
        await db.tasks.count_documents({**q, "kind": "meeting", "due_date": {"$regex": f"^{m}"}})
    rep_q = {"tenant_id": user["tenant_id"], "action": "REPORT", "at": {"$regex": f"^{m}"}, **({} if user["role"] == "admin" else {"user_id": user["id"]})}
    return {"clients": len(clients), "new_clients": sum(1 for c in clients if (c.get("created_at") or "").startswith(m)),
            "active_contract_clients": len(active), "meetings_month": meetings,
            "open_requests": await db.requests.count_documents({**q, "status": {"$in": ["new", "accepted", "reviewing"]}}),
            "waiting": await db.corrections.count_documents({**q, "status": "open"}) + await db.requests.count_documents({**q, "status": {"$in": ["in_progress", "meeting_scheduled"]}}),
            "reports_month": await db.audit_logs.count_documents(rep_q), "billing": await billing_summary(user)}


@router.get("/clients/overview")
async def clients_overview(user=Depends(staff)):
    from analytics import load
    from calc import data_health, positions
    data = await load(user)
    q = await scope(user, None)
    t = today()
    users = {u["id"]: u.get("name") for u in await db.users.find({"tenant_id": user["tenant_id"]}, {"id": 1, "name": 1}).to_list(1000)}
    cusers = await db.users.find({"tenant_id": user["tenant_id"], "role": "client"}, {"client_id": 1, "last_login": 1}).to_list(5000)
    contracts = await db.contracts.find(q).to_list(5000)
    invs = await db.invoices.find({**q, "status": {"$in": list(OPEN)}}).to_list(5000)
    tasks = await db.tasks.find({**q, "kind": "meeting", "status": {"$ne": "done"}, "due_date": {"$gte": t}}).to_list(5000)
    reqs = await db.requests.find({**q, "status": {"$in": ["new", "accepted", "reviewing", "in_progress"]}}, {"client_id": 1}).to_list(5000)
    docs = await db.documents.find(q).to_list(5000)
    out = []
    for c in data["clients"]:
        cid = c["id"]
        sub = {k: [x for x in data[k] if x.get("client_id") == cid] for k in ("accounts", "assets", "liabilities", "cashflows", "transactions", "goals", "consulting", "tasks")}
        sub["clients"] = [c]
        cons = [x for x in contracts if x["client_id"] == cid]
        last = await db.audit_logs.find_one({"tenant_id": user["tenant_id"], "client_id": cid, "user_role": "client",
                                             "action": {"$in": ["CREATE", "UPDATE", "DELETE", "UPLOAD"]}}, sort=[("at", -1)])
        mine = [x for x in invs if x["client_id"] == cid]
        h = data_health(sub, sub["transactions"], [d for d in docs if d["client_id"] == cid], positions(sub["transactions"], sub["assets"]))
        out.append({"id": cid, "name": c.get("corporate_name") or c.get("name"), "client_type": c.get("client_type"), "status": c.get("status"),
                    "contract_status": "ACTIVE" if any(x.get("status") == "ACTIVE" for x in cons) else (cons[-1].get("status") if cons else None),
                    "consultant": users.get(c.get("consultant_id")),
                    "last_login": max([u.get("last_login") or "" for u in cusers if u.get("client_id") == cid] or [""]) or None,
                    "last_update": (last or {}).get("at"),
                    "next_meeting": min([x["due_date"] for x in tasks if x.get("client_id") == cid] or [None], key=lambda v: v or "9999"),
                    "open_requests": sum(1 for r in reqs if r["client_id"] == cid),
                    "unpaid": sum(x["balance"] for x in mine), "overdue": any(x["due_date"] < t for x in mine),
                    "health": h["status"], "health_score": h["score"]})
    return out
