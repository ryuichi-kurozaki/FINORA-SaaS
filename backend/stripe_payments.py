"""Stripe card payments: (A) FINORA SaaS fee paid by tenant owner, (B) customer pays consultant invoice. Separate ledgers."""
import os
from datetime import date, timedelta
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, new_id, now_iso, current, admin_only, audit, notify, consultant_ids, client_user_ids
from billing import get_invoice, recompute

router = APIRouter(prefix="/api")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PAYABLE = ("ISSUED", "PARTIALLY_PAID", "OVERDUE")


class CheckoutIn(BaseModel):
    origin_url: str = Field(max_length=300)
    invoice_id: Optional[str] = None


def _session(name, amount, origin, meta, tax_code=None, tax_mode="none"):
    product = {"name": name[:200]} | ({"tax_code": tax_code} if tax_code else {})
    kwargs = dict(mode="payment", metadata=meta,
                  line_items=[{"quantity": 1, "price_data": {"currency": "jpy", "unit_amount": int(round(amount)), "product_data": product}}],
                  success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{origin}/payment/cancel")
    if tax_mode == "full":
        try:
            return stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError:
            pass
        try:
            return stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
        except stripe.error.InvalidRequestError:
            pass
    try:
        return stripe.checkout.Session.create(**kwargs)
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Stripe: {e.user_message or 'payment could not be started'}")


async def _record(session, kind, user, amount, extra):
    await db.payment_transactions.insert_one({
        "id": new_id(), "session_id": session.id, "kind": kind, "tenant_id": user["tenant_id"], "user_id": user["id"],
        "user_email": user["email"], "user_name": user.get("name"), "user_role": user["role"], "amount": float(amount), "currency": "jpy",
        "status": "initiated", "payment_status": "pending", "fulfilled": False, "created_at": now_iso(), "updated_at": now_iso(), **extra})


@router.post("/stripe/checkout/invoice")
async def checkout_invoice(body: CheckoutIn, user=Depends(current)):
    if user["role"] != "client":
        raise HTTPException(403, "Only the invoiced customer can pay by card")
    inv = await get_invoice(user, body.invoice_id or "")
    if inv["status"] not in PAYABLE or inv["balance"] <= 0:
        raise HTTPException(409, "This invoice is not payable")
    s = _session(f"Invoice {inv['number']}", inv["balance"], body.origin_url,
                 {"kind": "invoice", "invoice_id": inv["id"], "tenant_id": user["tenant_id"]})
    await _record(s, "invoice", user, inv["balance"], {"invoice_id": inv["id"], "client_id": inv["client_id"], "invoice_number": inv["number"]})
    return {"checkout_url": s.url, "session_id": s.id}


@router.post("/stripe/checkout/subscription")
async def checkout_subscription(body: CheckoutIn, user=Depends(admin_only)):
    sub = await db.saas_subscriptions.find_one({"tenant_id": user["tenant_id"]})
    if not sub or not sub.get("amount"):
        raise HTTPException(409, "FINORA fee has not been set for this account yet")
    s = _session(f"FINORA {sub.get('plan_code')} ({sub.get('billing_period', 'monthly')})", sub["amount"], body.origin_url,
                 {"kind": "subscription", "tenant_id": user["tenant_id"]}, tax_code="txcd_10103001", tax_mode="full")
    await _record(s, "subscription", user, sub["amount"], {"subscription_id": sub["id"]})
    return {"checkout_url": s.url, "session_id": s.id}


async def _fulfill(session_id, pi=None):
    tx = await db.payment_transactions.find_one_and_update(
        {"session_id": session_id, "fulfilled": {"$ne": True}},
        {"$set": {"fulfilled": True, "status": "completed", "payment_status": "paid", "stripe_payment_intent_id": pi, "updated_at": now_iso()}})
    if not tx:
        return
    actor = {"id": tx["user_id"], "tenant_id": tx["tenant_id"], "email": tx["user_email"], "name": tx.get("user_name"), "role": tx["user_role"]}
    tid = tx["tenant_id"]
    if tx["kind"] == "invoice":
        inv = await db.invoices.find_one({"id": tx["invoice_id"], "tenant_id": tid})
        doc = {"id": new_id(), "tenant_id": tid, "client_id": inv["client_id"], "invoice_id": inv["id"], "invoice_number": inv["number"],
               "date": date.today().isoformat(), "amount": tx["amount"], "method": "CREDIT_CARD", "reference": pi or session_id,
               "notes": "Stripe", "source": "STRIPE", "created_by": actor["id"], "created_by_name": actor["name"], "created_at": now_iso()}
        await db.payments.insert_one(doc)
        await recompute(inv["id"])
        doc.pop("_id", None)
        await audit(actor, "create", "payments", doc["id"], after=dict(doc), client_id=inv["client_id"], label=f"{inv['number']} ¥{tx['amount']:,.0f} (card)")
        ids = await consultant_ids(tid, inv["client_id"]) + await client_user_ids(tid, inv["client_id"])
        owners = [u["id"] for u in await db.users.find({"tenant_id": tid, "role": "admin"}, {"id": 1}).to_list(20)]
        await notify(tid, ids + owners, "payment_confirmed", {"label": inv["number"], "amount": tx["amount"]}, inv["client_id"], "/billing")
    else:
        sub = await db.saas_subscriptions.find_one({"tenant_id": tid})
        days = 365 if sub.get("billing_period") == "yearly" else 30
        start = max(date.today().isoformat(), sub.get("renewal_date") or "")
        renewal = (date.fromisoformat(start) + timedelta(days=days)).isoformat()
        upd = {"payment_status": "paid", "status": "ACTIVE", "renewal_date": renewal, "last_paid_at": now_iso()}
        await db.saas_subscriptions.update_one({"id": sub["id"]}, {"$set": upd})
        await db.tenants.update_one({"id": tid, "status": "TRIAL"}, {"$set": {"status": "ACTIVE"}})
        await audit(actor, "payment", "saas_subscriptions", sub["id"], before={k: sub.get(k) for k in upd}, after=upd, label=f"FINORA fee ¥{tx['amount']:,.0f} (card)")


@router.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx:
        raise HTTPException(404, "Transaction not found")
    if tx.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await _fulfill(session_id, s.payment_intent)
            elif s.status == "expired":
                await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"status": "expired", "payment_status": "expired"}})
        except stripe.error.StripeError:
            pass
        tx = await db.payment_transactions.find_one({"session_id": session_id})
    return {"session_id": session_id, "status": tx["status"], "payment_status": tx["payment_status"]}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), WEBHOOK_SECRET)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded") and obj.get("payment_status") == "paid":
        await _fulfill(obj["id"], obj.get("payment_intent"))
    elif t in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        st = "failed" if t.endswith("failed") else "expired"
        await db.payment_transactions.update_one({"session_id": obj["id"], "payment_status": {"$ne": "paid"}}, {"$set": {"status": st, "payment_status": st}})
    return {"status": "ok"}
