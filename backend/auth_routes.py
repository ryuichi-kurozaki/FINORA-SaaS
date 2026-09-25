from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, Field

from core import (db, now, now_iso, new_id, clean, hash_password, verify_password, make_token, decode_token,
                  ip_of, current, staff, admin_only, audit, ACCESS_MIN, REFRESH_DAYS)

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
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0})
    return {**user, "tenant": tenant}


@router.post("/auth/change-password")
async def change_password(body: PasswordIn, request: Request, user=Depends(current)):
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
    return {"ok": True}


@router.get("/users")
async def list_users(user=Depends(staff)):
    q = {"tenant_id": user["tenant_id"]}
    if user["role"] != "admin":
        q["role"] = {"$in": ["admin", "consultant"]}
    return [clean(u) for u in await db.users.find(q).sort("created_at", 1).to_list(1000)]


@router.post("/users")
async def create_user(body: UserIn, request: Request, user=Depends(admin_only)):
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
