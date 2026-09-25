"""Tenancy: consultant signup (own tenant), customer invitations, FINORA SaaS plans/subscriptions (separate ledger), platform admin."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import (forbid_demo, db, new_id, now, now_iso, clean, staff, admin_only, platform_admin, scope, audit, notify, hash_password,
                  encrypt, ip_of)

router = APIRouter(prefix="/api")
TENANT_STATUS = ("TRIAL", "ACTIVE", "SUSPENDED", "CANCELLED")


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def inv_status(i):
    if i["status"] == "PENDING" and i.get("expires_at", "") < now_iso():
        return "EXPIRED"
    return i["status"]


@router.get("/public/plans")
async def public_plans():
    return [clean(p) for p in await db.plans.find({"active": True}).sort("order", 1).to_list(50)]


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    company_name: str = Field("", max_length=150)
    entity_type: str = "individual"
    email: str = Field(min_length=5, max_length=200)
    phone: str = Field("", max_length=40)
    address: str = Field("", max_length=300)
    profile: str = Field("", max_length=2000)
    qualifications: str = Field("", max_length=500)
    plan_code: str = "TRIAL"
    password: str = Field(min_length=8, max_length=128)


@router.post("/public/signup")
async def signup(body: SignupIn, request: Request):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422, "Invalid email")
    ip = ip_of(request)
    if await db.tenants.count_documents({"signup_ip": ip, "created_at": {"$gt": (now() - timedelta(hours=1)).isoformat()}}) >= 5:
        raise HTTPException(429, "Too many signups. Please try again later.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "This email is already registered")
    plan = await db.plans.find_one({"code": body.plan_code, "active": True}) or await db.plans.find_one({"code": "TRIAL"})
    tid, uid = new_id(), new_id()
    status = "TRIAL" if plan["code"] in ("TRIAL", "FREE") else "ACTIVE"
    await db.tenants.insert_one({"id": tid, "slug": tid[:8], "name": body.company_name or body.name, "entity_type": body.entity_type,
                                 "owner_user_id": uid, "status": status, "signup_ip": ip, "created_at": now_iso(),
                                 "billing_profile": {"company_name": body.company_name or body.name, "representative": body.name,
                                                     "address": body.address, "phone": body.phone, "email": email}})
    user = {"id": uid, "tenant_id": tid, "email": email, "name": body.name, "role": "admin", "active": True,
            "password_hash": hash_password(body.password), "phone": encrypt(body.phone), "address": encrypt(body.address),
            "profile": body.profile, "qualifications": body.qualifications, "created_at": now_iso()}
    await db.users.insert_one(user)
    start = datetime.now().date()
    await db.saas_subscriptions.insert_one({"id": new_id(), "tenant_id": tid, "plan_code": plan["code"], "start_date": start.isoformat(),
                                            "renewal_date": (start + timedelta(days=30)).isoformat(), "billing_period": "monthly",
                                            "amount": plan.get("price_monthly"), "status": status, "payment_status": "none", "created_at": now_iso()})
    await db.settings.insert_one({"tenant_id": tid, "fx": {}, "base_currency": "JPY"})
    await audit(user, "signup", "tenants", tid, after={"name": body.company_name or body.name, "plan": plan["code"], "status": status}, request=request)
    return {"ok": True, "tenant_id": tid}


class InviteIn(BaseModel):
    client_id: str
    email: str = Field(min_length=5, max_length=200)


@router.post("/invitations")
async def create_invitation(body: InviteIn, request: Request, user=Depends(staff)):
    forbid_demo(user)
    await scope(user, body.client_id)
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "This email already has a FINORA account")
    await db.invitations.update_many({"tenant_id": user["tenant_id"], "client_id": body.client_id, "status": "PENDING"}, {"$set": {"status": "CANCELLED"}})
    token = secrets.token_urlsafe(24)
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], "client_id": body.client_id, "email": email, "token_hash": _hash(token),
           "invited_by": user["id"], "invited_by_name": user.get("name"), "status": "PENDING", "created_at": now_iso(),
           "expires_at": (now() + timedelta(days=7)).isoformat()}
    await db.invitations.insert_one(doc)
    await audit(user, "invite", "invitations", doc["id"], after={"email": email}, request=request, client_id=body.client_id, label=email)
    return clean({k: v for k, v in doc.items() if k != "token_hash"}) | {"token": token, "path": f"/invite/{token}"}


@router.get("/invitations")
async def list_invitations(client_id: Optional[str] = None, user=Depends(staff)):
    q = await scope(user, client_id)
    return [clean({k: v for k, v in i.items() if k != "token_hash"}) | {"status": inv_status(i)} for i in await db.invitations.find(q).sort("created_at", -1).to_list(2000)]


@router.post("/invitations/{iid}/cancel")
async def cancel_invitation(iid: str, request: Request, user=Depends(staff)):
    i = await db.invitations.find_one({"id": iid, "tenant_id": user["tenant_id"]})
    if not i:
        raise HTTPException(404, "Not found")
    await scope(user, i["client_id"])
    await db.invitations.update_one({"id": iid}, {"$set": {"status": "CANCELLED"}})
    await audit(user, "cancel", "invitations", iid, before={"status": i["status"]}, after={"status": "CANCELLED"}, request=request, client_id=i["client_id"], label=i["email"])
    return {"ok": True}


async def _by_token(token):
    i = await db.invitations.find_one({"token_hash": _hash(token)})
    if not i:
        raise HTTPException(404, "Invitation not found")
    return i


@router.get("/public/invitations/{token}")
async def invitation_info(token: str):
    i = await _by_token(token)
    t = await db.tenants.find_one({"id": i["tenant_id"]}, {"name": 1})
    c = await db.clients.find_one({"id": i["client_id"]}, {"name": 1, "corporate_name": 1})
    return {"email": i["email"], "status": inv_status(i), "expires_at": i["expires_at"], "tenant_name": (t or {}).get("name"),
            "client_name": (c or {}).get("corporate_name") or (c or {}).get("name"), "inviter": i.get("invited_by_name")}


class AcceptIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


@router.post("/public/invitations/{token}/accept")
async def accept_invitation(token: str, body: AcceptIn, request: Request):
    i = await _by_token(token)
    if inv_status(i) != "PENDING":
        raise HTTPException(410, "Invitation is no longer valid")
    if await db.users.find_one({"email": i["email"]}):
        raise HTTPException(409, "This email already has a FINORA account")
    user = {"id": new_id(), "tenant_id": i["tenant_id"], "email": i["email"], "name": body.name, "role": "client", "client_id": i["client_id"],
            "active": True, "password_hash": hash_password(body.password), "created_at": now_iso()}
    await db.users.insert_one(user)
    await db.invitations.update_one({"id": i["id"]}, {"$set": {"status": "ACCEPTED", "accepted_at": now_iso(), "user_id": user["id"]}})
    await audit(user, "accept", "invitations", i["id"], after={"email": i["email"]}, request=request, client_id=i["client_id"], label=i["email"])
    await notify(i["tenant_id"], [i["invited_by"]], "invitation_accepted", {"label": body.name}, i["client_id"], f"/clients/{i['client_id']}")
    return {"ok": True, "email": i["email"]}


@router.get("/subscription")
async def my_subscription(user=Depends(admin_only)):
    t = await db.tenants.find_one({"id": user["tenant_id"]}) or {}
    s = await db.saas_subscriptions.find_one({"tenant_id": user["tenant_id"]}) or {}
    p = await db.plans.find_one({"code": s.get("plan_code")}) or {}
    return {"tenant": {"name": t.get("name"), "status": t.get("status")}, "subscription": clean(s), "plan": clean(p)}


@router.get("/platform/tenants")
async def platform_tenants(user=Depends(platform_admin)):
    out = []
    for t in await db.tenants.find().sort("created_at", -1).to_list(2000):
        s = await db.saas_subscriptions.find_one({"tenant_id": t["id"]}) or {}
        owner = await db.users.find_one({"id": t.get("owner_user_id")}, {"name": 1, "email": 1}) or {}
        last = await db.audit_logs.find_one({"tenant_id": t["id"]}, sort=[("at", -1)])
        out.append({"id": t["id"], "name": t.get("name"), "status": t.get("status", "ACTIVE"), "owner_name": owner.get("name"), "owner_email": owner.get("email"),
                    "plan_code": s.get("plan_code"), "subscription_status": s.get("status"), "payment_status": s.get("payment_status"),
                    "amount": s.get("amount"), "billing_period": s.get("billing_period"), "renewal_date": s.get("renewal_date"),
                    "members": await db.users.count_documents({"tenant_id": t["id"], "role": {"$ne": "client"}}),
                    "customers": await db.clients.count_documents({"tenant_id": t["id"]}),
                    "last_activity": (last or {}).get("at"), "created_at": t.get("created_at")})
    return out


class TenantUpd(BaseModel):
    status: Optional[str] = None
    plan_code: Optional[str] = None
    renewal_date: Optional[str] = None
    amount: Optional[float] = None
    billing_period: Optional[str] = None
    payment_status: Optional[str] = None


@router.put("/platform/tenants/{tid}")
async def platform_update_tenant(tid: str, body: TenantUpd, request: Request, user=Depends(platform_admin)):
    t = await db.tenants.find_one({"id": tid})
    if not t:
        raise HTTPException(404, "Not found")
    if body.status and body.status not in TENANT_STATUS:
        raise HTTPException(422, "Invalid status")
    before = clean(await db.saas_subscriptions.find_one({"tenant_id": tid}) or {}) | {"tenant_status": t.get("status")}
    sub = {k: v for k, v in body.model_dump().items() if v is not None and k != "status"}
    if body.status:
        sub["status"] = body.status
        await db.tenants.update_one({"id": tid}, {"$set": {"status": body.status}})
        if body.status in ("SUSPENDED", "CANCELLED"):
            ids = [u["id"] for u in await db.users.find({"tenant_id": tid}, {"id": 1}).to_list(5000)]
            await db.sessions.update_many({"user_id": {"$in": ids}}, {"$set": {"revoked": True}})
    if sub:
        await db.saas_subscriptions.update_one({"tenant_id": tid}, {"$set": sub}, upsert=True)
    await audit(user, "update", "saas_subscriptions", tid, before=before, after=body.model_dump(exclude_none=True), request=request, label=t.get("name"))
    return {"ok": True}


@router.get("/platform/plans")
async def platform_plans(user=Depends(platform_admin)):
    return [clean(p) for p in await db.plans.find().sort("order", 1).to_list(50)]


class PlanUpd(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    max_customers: Optional[int] = None
    active: Optional[bool] = None


@router.put("/platform/plans/{code}")
async def platform_update_plan(code: str, body: PlanUpd, request: Request, user=Depends(platform_admin)):
    p = await db.plans.find_one({"code": code})
    if not p:
        raise HTTPException(404, "Not found")
    upd = body.model_dump(exclude_none=True)
    await db.plans.update_one({"code": code}, {"$set": upd})
    await audit(user, "update", "plans", code, before=clean(dict(p)), after=upd, request=request, label=code)
    return {"ok": True}


@router.get("/platform/audit")
async def platform_audit(user=Depends(platform_admin)):
    logs = await db.audit_logs.find({"entity": {"$in": ["tenants", "plans", "saas_subscriptions"]}}, {"before": 0}).sort("at", -1).to_list(300)
    return [clean(x) for x in logs]
