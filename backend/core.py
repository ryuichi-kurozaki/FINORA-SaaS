import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Request, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet, InvalidToken

mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo[os.environ["DB_NAME"]]
log = logging.getLogger("finora")

JWT_ALG = "HS256"
ACCESS_MIN = 60
REFRESH_DAYS = 7
_fernet = Fernet(os.environ["FIELD_ENCRYPTION_KEY"].encode())


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat()


def new_id():
    return str(uuid.uuid4())


def clean(doc):
    if doc:
        doc.pop("_id", None)
        for k in ("password_hash", "totp_secret", "totp_pending", "payout_bank"):
            doc.pop(k, None)
    return doc


def encrypt(v):
    if v in (None, ""):
        return v
    return "enc:" + _fernet.encrypt(str(v).encode()).decode()


def decrypt(v):
    if isinstance(v, str) and v.startswith("enc:"):
        try:
            return _fernet.decrypt(v[4:].encode()).decode()
        except InvalidToken:
            return ""
    return v


def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())


def make_token(uid, sid, kind):
    exp = now() + {"access": timedelta(minutes=ACCESS_MIN), "2fa": timedelta(minutes=5)}.get(kind, timedelta(days=REFRESH_DAYS))
    return jwt.encode({"sub": uid, "sid": sid, "type": kind, "exp": exp}, os.environ["JWT_SECRET"], algorithm=JWT_ALG)


def decode_token(token, kind):
    try:
        p = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    if p.get("type") != kind:
        raise HTTPException(401, "Invalid token type")
    return p


def ip_of(request: Request):
    fwd = request.headers.get("x-forwarded-for")
    return (fwd or (request.client.host if request.client else "")).split(",")[0].strip()


async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    p = decode_token(token, "access")
    if not await db.sessions.find_one({"id": p["sid"], "revoked": False}):
        raise HTTPException(401, "Session revoked")
    user = await db.users.find_one({"id": p["sub"], "active": True})
    if not user:
        raise HTTPException(401, "User not found")
    user["sid"] = p["sid"]
    return clean(user)


def require_roles(*roles):
    async def dep(request: Request):
        user = await get_current_user(request)
        if user["role"] not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return dep


def forbid_demo(user):
    if user.get("demo"):
        raise HTTPException(403, "デモアカウントではこの操作はできません (Not available in the demo account)")


async def require_service(user):
    t = await db.tenants.find_one({"id": user["tenant_id"]}, {"finora_contract_required": 1, "finora_contract": 1})
    if t and t.get("finora_contract_required") and t.get("finora_contract") != "ACTIVE":
        raise HTTPException(403, "FINORA利用契約の成立後に利用できます (Available after the FINORA service agreement is executed)")


current = require_roles("admin", "consultant", "client")
staff = require_roles("admin", "consultant")
admin_only = require_roles("admin")


async def track_peak(tenant_id):
    """Records this month's peak customer count (billing basis) and returns (current, peak)."""
    from datetime import datetime as _dt
    from pymongo import ReturnDocument
    cur = await db.clients.count_documents({"tenant_id": tenant_id})
    doc = await db.customer_peaks.find_one_and_update({"tenant_id": tenant_id, "month": _dt.now().strftime("%Y-%m")}, {"$max": {"peak": cur}},
                                                     upsert=True, return_document=ReturnDocument.AFTER)
    return cur, doc["peak"]


def sees_all(user):
    return user["role"] == "admin" and not user.get("is_consultant")


async def accessible_ids(user):
    if sees_all(user):
        return None
    if user["role"] == "client":
        return [user.get("client_id")]
    cs = await db.clients.find({"tenant_id": user["tenant_id"], "$or": [{"consultant_id": user["id"]}, {"secondary_consultant_ids": user["id"]}]}, {"id": 1}).to_list(5000)
    return [c["id"] for c in cs]


async def platform_admin(request: Request):
    user = await get_current_user(request)
    if not user.get("platform_admin"):
        raise HTTPException(403, "FINORA platform admin only")
    return user


async def scope(user, client_id=None):
    ids = await accessible_ids(user)
    q = {"tenant_id": user["tenant_id"]}
    if client_id:
        if ids is not None and client_id not in ids:
            raise HTTPException(403, "No access to this client")
        q["client_id"] = client_id
    elif ids is not None:
        q["client_id"] = {"$in": ids}
    return q


def _label(d):
    if isinstance(d, dict):
        for k in ("title", "name", "institution", "filename", "target_label", "tx_type", "category"):
            if d.get(k) and not str(d[k]).startswith("enc:"):
                return str(d[k])[:120]
    return None


async def audit(user, action, entity, entity_id, before=None, after=None, request=None, client_id=None, label=None):
    for d in (before, after):
        if isinstance(d, dict):
            d.pop("_id", None)
    if client_id is None:
        client_id = entity_id if entity == "clients" else next(
            (d.get("client_id") for d in (after, before) if isinstance(d, dict) and d.get("client_id")), None)
    await db.audit_logs.insert_one({
        "id": new_id(), "tenant_id": user["tenant_id"], "user_id": user["id"], "user_email": user["email"],
        "user_name": user.get("name"), "user_role": user.get("role"), "action": action.upper(), "entity": entity,
        "entity_id": entity_id, "client_id": client_id, "label": label or _label(after) or _label(before),
        "before": before, "after": after, "ip": ip_of(request) if request else None, "at": now_iso(),
    })


async def client_user_ids(tenant_id, client_id):
    return [u["id"] for u in await db.users.find({"tenant_id": tenant_id, "client_id": client_id, "role": "client", "active": True}, {"id": 1}).to_list(50)]


async def consultant_ids(tenant_id, client_id):
    c = await db.clients.find_one({"tenant_id": tenant_id, "id": client_id}, {"consultant_id": 1})
    return [c["consultant_id"]] if c and c.get("consultant_id") else []


async def notify(tenant_id, user_ids, kind, params=None, client_id=None, link=None, actor=None):
    docs = [{"id": new_id(), "tenant_id": tenant_id, "user_id": u, "kind": kind, "params": params or {}, "client_id": client_id,
             "link": link, "actor_name": (actor or {}).get("name"), "read": False, "created_at": now_iso()}
            for u in set(user_ids) if u and u != (actor or {}).get("id")]
    if docs:
        await db.notifications.insert_many(docs)


async def notify_other_side(user, client_id, kind, params=None, link=None):
    ids = await consultant_ids(user["tenant_id"], client_id) if user["role"] == "client" else await client_user_ids(user["tenant_id"], client_id)
    await notify(user["tenant_id"], ids, kind, params, client_id, link, user)
