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
        doc.pop("password_hash", None)
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
    exp = now() + (timedelta(minutes=ACCESS_MIN) if kind == "access" else timedelta(days=REFRESH_DAYS))
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


current = require_roles("admin", "consultant", "client")
staff = require_roles("admin", "consultant")
admin_only = require_roles("admin")


async def accessible_ids(user):
    if user["role"] == "admin":
        return None
    if user["role"] == "client":
        return [user.get("client_id")]
    cs = await db.clients.find({"tenant_id": user["tenant_id"], "consultant_id": user["id"]}, {"id": 1}).to_list(5000)
    return [c["id"] for c in cs]


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


async def audit(user, action, entity, entity_id, before=None, after=None, request=None):
    for d in (before, after):
        if isinstance(d, dict):
            d.pop("_id", None)
    await db.audit_logs.insert_one({
        "id": new_id(), "tenant_id": user["tenant_id"], "user_id": user["id"], "user_email": user["email"],
        "action": action, "entity": entity, "entity_id": entity_id, "before": before, "after": after,
        "ip": ip_of(request) if request else None, "at": now_iso(),
    })
