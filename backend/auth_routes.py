from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, Field

import re
import pyotp

from core import (forbid_demo, db, now, now_iso, new_id, clean, hash_password, verify_password, make_token, decode_token,
                  ip_of, current, staff, admin_only, audit, encrypt, decrypt, ACCESS_MIN, REFRESH_DAYS)

router = APIRouter(prefix="/api")
MAX_ATTEMPTS = 5
LOCK_MIN = 15
ROLES = ("admin", "consultant", "client")


class LoginIn(BaseModel):
    email: str
    password: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserIn(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    active: Optional[bool] = None
    lang: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    whatsapp_opt_in: Optional[bool] = None
    line_id: Optional[str] = Field(None, max_length=60)


def set_cookies(resp, access, refresh=None):
    resp.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=ACCESS_MIN * 60, path="/")
    if refresh:
        resp.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=REFRESH_DAYS * 86400, path="/")


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email, ip, ua = body.email.strip().lower(), ip_of(request), request.headers.get("user-agent", "")
    ident = f"{ip}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until") and att["locked_until"] > now_iso():
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not user.get("active", True) or not verify_password(body.password, user["password_hash"]):
        count = (att or {}).get("count", 0) + 1
        upd = {"count": count}
        if count >= MAX_ATTEMPTS:
            upd = {"count": 0, "locked_until": (now() + timedelta(minutes=LOCK_MIN)).isoformat()}
        await db.login_attempts.update_one({"identifier": ident}, {"$set": upd}, upsert=True)
        await db.login_history.insert_one({"id": new_id(), "tenant_id": user["tenant_id"] if user else None,
                                           "user_id": user["id"] if user else None, "email": email, "ip": ip, "ua": ua,
                                           "success": False, "anomaly": count >= 3,
                                           "reason": "repeated_failure" if count >= 3 else "bad_credentials", "at": now_iso()})
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"identifier": ident})
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"status": 1, "end_policy": 1, "finora_contract": 1})
    if tenant and tenant.get("status") in ("SUSPENDED", "CANCELLED") and not user.get("platform_admin"):
        raise HTTPException(403, "This FINORA account is suspended. Please contact support.")
    pol = (tenant or {}).get("end_policy") or {}
    if (tenant or {}).get("finora_contract") == "ENDED" and pol.get("client_access" if user["role"] == "client" else "consultant_login") == "blocked":
        raise HTTPException(403, "The FINORA service agreement has ended")
    if user.get("totp_enabled"):
        return {"requires_2fa": True, "challenge_token": make_token(user["id"], None, "2fa")}
    return await complete_login(user, request, response)


class TwoFAIn(BaseModel):
    challenge_token: str
    code: str


class CodeIn(BaseModel):
    code: str


def _totp_ok(secret_enc, code):
    return bool(secret_enc) and pyotp.TOTP(decrypt(secret_enc)).verify(str(code).strip(), valid_window=1)


@router.post("/auth/2fa/verify")
async def verify_2fa(body: TwoFAIn, request: Request, response: Response):
    p = decode_token(body.challenge_token, "2fa")
    ident = f"2fa:{p['sub']}"
    att = await db.login_attempts.find_one({"identifier": ident}) or {}
    if att.get("count", 0) >= MAX_ATTEMPTS:
        raise HTTPException(429, "Too many attempts. Please log in again later.")
    user = await db.users.find_one({"id": p["sub"], "active": True})
    if not user or not _totp_ok(user.get("totp_secret"), body.code):
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}}, upsert=True)
        raise HTTPException(401, "Invalid authentication code")
    await db.login_attempts.delete_one({"identifier": ident})
    return await complete_login(user, request, response)


@router.post("/auth/2fa/setup")
async def setup_2fa(user=Depends(current)):
    forbid_demo(user)
    secret = pyotp.random_base32()
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_pending": encrypt(secret)}})
    return {"secret": secret, "uri": pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="FINORA")}


@router.post("/auth/2fa/enable")
async def enable_2fa(body: CodeIn, request: Request, user=Depends(current)):
    forbid_demo(user)
    u = await db.users.find_one({"id": user["id"]})
    if not _totp_ok(u.get("totp_pending"), body.code):
        raise HTTPException(400, "Invalid authentication code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_secret": u["totp_pending"], "totp_enabled": True}, "$unset": {"totp_pending": ""}})
    await audit(user, "update", "users", user["id"], before={"totp_enabled": False}, after={"totp_enabled": True}, request=request)
    return {"ok": True}


@router.post("/auth/2fa/disable")
async def disable_2fa(body: CodeIn, request: Request, user=Depends(current)):
    forbid_demo(user)
    u = await db.users.find_one({"id": user["id"]})
    if not _totp_ok(u.get("totp_secret"), body.code):
        raise HTTPException(400, "Invalid authentication code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_enabled": False}, "$unset": {"totp_secret": ""}})
    await audit(user, "update", "users", user["id"], before={"totp_enabled": True}, after={"totp_enabled": False}, request=request)
    return {"ok": True}


async def complete_login(user, request, response):
    email, ip, ua = user["email"], ip_of(request), request.headers.get("user-agent", "")
    first = not await db.login_history.find_one({"user_id": user["id"], "success": True})
    known = await db.login_history.find_one({"user_id": user["id"], "success": True, "ip": ip})
    anomaly = not first and not known
    sid = new_id()
    await db.sessions.insert_one({"id": sid, "user_id": user["id"], "tenant_id": user["tenant_id"], "ip": ip, "ua": ua,
                                  "created_at": now_iso(), "revoked": False})
    await db.login_history.insert_one({"id": new_id(), "tenant_id": user["tenant_id"], "user_id": user["id"], "email": email,
                                       "ip": ip, "ua": ua, "success": True, "anomaly": anomaly,
                                       "reason": "new_ip" if anomaly else None, "at": now_iso()})
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login": now_iso()}})
    access, refresh = make_token(user["id"], sid, "access"), make_token(user["id"], sid, "refresh")
    set_cookies(response, access, refresh)
    await audit(user, "login", "sessions", sid, after={"ip": ip, "anomaly": anomaly}, request=request, client_id=user.get("client_id"))
    return {"user": clean(user), "access_token": access}


@router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "No refresh token")
    p = decode_token(token, "refresh")
    if not await db.sessions.find_one({"id": p["sid"], "revoked": False}):
        raise HTTPException(401, "Session revoked")
    access = make_token(p["sub"], p["sid"], "access")
    set_cookies(response, access)
    return {"access_token": access}


@router.post("/auth/logout")
async def logout(response: Response, user=Depends(current)):
    await db.sessions.update_one({"id": user["sid"]}, {"$set": {"revoked": True}})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
async def me(user=Depends(current)):
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0, "payout_bank": 0})
    reg = bool((await db.users.find_one({"id": user["id"]}, {"payout_bank": 1}) or {}).get("payout_bank"))
    return {**{k: v for k, v in user.items() if k != "payout_bank"}, "tenant": tenant, "payout_bank_registered": reg}


@router.post("/auth/change-password")
async def change_password(body: PasswordIn, request: Request, user=Depends(current)):
    forbid_demo(user)
    u = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.current_password, u["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    await audit(user, "change_password", "users", user["id"], request=request)
    return {"ok": True}


@router.put("/auth/preferences")
async def prefs(body: UserIn, user=Depends(current)):
    if body.lang in ("ja", "en", "pt"):
        await db.users.update_one({"id": user["id"]}, {"$set": {"lang": body.lang}})
    if body.whatsapp_phone is not None:
        p = re.sub(r"[\s\-()]", "", body.whatsapp_phone)
        if p and not re.fullmatch(r"\+?[1-9]\d{7,14}", p):
            raise HTTPException(422, "WhatsApp number must include the country code, e.g. +81 90 1234 5678")
        if body.whatsapp_opt_in and not p:
            raise HTTPException(422, "Enter your WhatsApp number to turn on WhatsApp notifications")
        await db.users.update_one({"id": user["id"]}, {"$set": {"whatsapp_phone": p.lstrip("+"), "whatsapp_opt_in": bool(body.whatsapp_opt_in)}})
    if body.line_id is not None:
        await db.users.update_one({"id": user["id"]}, {"$set": {"line_id": body.line_id.strip()}})
    u = await db.users.find_one({"id": user["id"]})
    return {"ok": True, "lang": u.get("lang"), "whatsapp_phone": u.get("whatsapp_phone"), "whatsapp_opt_in": bool(u.get("whatsapp_opt_in")), "line_id": u.get("line_id")}


@router.get("/users")
async def list_users(user=Depends(staff)):
    q = {"tenant_id": user["tenant_id"]}
    if user["role"] != "admin":
        q["role"] = {"$in": ["admin", "consultant"]}
    return [clean(u) for u in await db.users.find(q).sort("created_at", 1).to_list(1000)]


@router.post("/users")
async def create_user(body: UserIn, request: Request, user=Depends(admin_only)):
    forbid_demo(user)
    if not body.email or not body.password or body.role not in ROLES:
        raise HTTPException(422, "email, password and valid role are required")
    if len(body.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Email already exists")
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], "email": email, "name": body.name or email,
           "role": body.role, "client_id": body.client_id if body.role == "client" else None, "active": True,
           "lang": body.lang or "ja", "password_hash": hash_password(body.password), "created_at": now_iso()}
    await db.users.insert_one(doc)
    safe = clean(dict(doc))
    await audit(user, "create", "users", doc["id"], after=safe, request=request)
    return safe


@router.put("/users/{uid}")
async def update_user(uid: str, body: UserIn, request: Request, user=Depends(admin_only)):
    forbid_demo(user)
    before = clean(await db.users.find_one({"id": uid, "tenant_id": user["tenant_id"]}))
    if not before:
        raise HTTPException(404, "User not found")
    upd = {k: v for k, v in body.model_dump().items() if v is not None and k in ("name", "role", "client_id", "active", "lang")}
    if "role" in upd and upd["role"] not in ROLES:
        raise HTTPException(422, "Invalid role")
    if uid == user["id"] and (upd.get("active") is False or upd.get("role", "admin") != "admin"):
        raise HTTPException(400, "You cannot demote or deactivate yourself")
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(422, "Password must be at least 8 characters")
        upd["password_hash"] = hash_password(body.password)
    await db.users.update_one({"id": uid}, {"$set": upd})
    if upd.get("active") is False:
        await db.sessions.update_many({"user_id": uid}, {"$set": {"revoked": True}})
    after = clean(await db.users.find_one({"id": uid}))
    await audit(user, "update", "users", uid, before=before, after=after, request=request)
    return after


@router.get("/security/login-history")
async def login_history(user=Depends(current)):
    q = {"tenant_id": user["tenant_id"]} if user["role"] == "admin" else {"user_id": user["id"]}
    return [clean(x) for x in await db.login_history.find(q).sort("at", -1).to_list(300)]


@router.get("/security/audit-logs")
async def audit_logs(entity: Optional[str] = None, user=Depends(admin_only)):
    q = {"tenant_id": user["tenant_id"]}
    if entity:
        q["entity"] = entity
    return [clean(x) for x in await db.audit_logs.find(q).sort("at", -1).to_list(500)]


@router.get("/security/sessions")
async def sessions(user=Depends(current)):
    items = await db.sessions.find({"user_id": user["id"], "revoked": False}).sort("created_at", -1).to_list(100)
    return [{**clean(s), "current": s["id"] == user["sid"]} for s in items]


@router.delete("/security/sessions/{sid}")
async def revoke_session(sid: str, request: Request, user=Depends(current)):
    await db.sessions.update_one({"id": sid, "user_id": user["id"]}, {"$set": {"revoked": True}})
    await audit(user, "revoke_session", "sessions", sid, request=request)
    return {"ok": True}
