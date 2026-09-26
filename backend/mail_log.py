"""Email delivery log: send results (db.email_log) + final Postfix delivery status parsed from MAIL_LOG_PATH."""
import asyncio
import logging
import os
import re

from fastapi import APIRouter, Depends

from core import db, now_iso, platform_admin

router = APIRouter(prefix="/api/platform/email-log")
logger = logging.getLogger(__name__)
MAIL_LOG_PATH = os.environ["MAIL_LOG_PATH"]
KEY = "mail_log"
STATUSES = ("queued", "delivered", "deferred", "bounced", "failed", "logged")
KINDS = ("invite", "econtract", "renewal", "invoice", "refund", "inquiry", "system", "other")
RE_MSGID = re.compile(r"postfix/cleanup\[\d+\]: ([0-9A-Za-z]+): message-id=<?([^>\s]+)>?")
RE_STATUS = re.compile(r"postfix/[\w-]+\[\d+\]: ([0-9A-Za-z]+): to=<([^>]*)>.*?(?:dsn=([\d.]+), )?status=(\w+) ?(.*)$")
RE_EXPIRED = re.compile(r"postfix/qmgr\[\d+\]: ([0-9A-Za-z]+): from=<[^>]*>, status=expired(.*)$")
MAP = {"sent": "delivered", "deferred": "deferred", "bounced": "bounced", "expired": "bounced"}


def parse(lines):
    """Returns ({queue_id: message_id}, {queue_id: (status, detail)}) — last status per queue id wins."""
    ids, st = {}, {}
    for ln in lines:
        if m := RE_MSGID.search(ln):
            ids[m.group(1)] = m.group(2)
        elif m := RE_STATUS.search(ln):
            if m.group(4) in MAP:
                st[m.group(1)] = (MAP[m.group(4)], f"{('dsn=' + m.group(3) + ' ') if m.group(3) else ''}{m.group(5).strip()}"[:300])
        elif m := RE_EXPIRED.search(ln):
            st[m.group(1)] = ("bounced", ("expired " + m.group(2).strip(" ,"))[:300])
    return ids, st


def _read(path, offset):
    with open(path, "rb") as f:
        f.seek(offset)
        data = f.read()
    return data.decode("utf-8", "replace").splitlines(), offset + len(data)


async def apply(lines):
    ids, st = parse(lines)
    for qid, mid in ids.items():
        await db.email_log.update_many({"message_id": mid}, {"$set": {"queue_id": qid}})
    n = 0
    for qid, (status, detail) in st.items():
        r = await db.email_log.update_many({"queue_id": qid}, {"$set": {"status": status, "detail": detail, "updated_at": now_iso()}})
        n += r.modified_count
    return n


async def sync():
    """Reads new Postfix log lines since the last run (handles logrotate via inode)."""
    if not MAIL_LOG_PATH or not os.path.exists(MAIL_LOG_PATH):
        return {"enabled": False, "updated": 0}
    s = await db.system_state.find_one({"id": KEY}) or {}
    ino, size = os.stat(MAIL_LOG_PATH).st_ino, os.path.getsize(MAIL_LOG_PATH)
    lines, offset = [], s.get("offset", 0)
    if s.get("inode") and s["inode"] != ino:
        old = MAIL_LOG_PATH + ".1"
        if os.path.exists(old) and os.stat(old).st_ino == s["inode"]:
            lines, _ = await asyncio.to_thread(_read, old, offset)
        offset = 0
    if offset > size:
        offset = 0
    new, offset = await asyncio.to_thread(_read, MAIL_LOG_PATH, offset)
    n = await apply(lines + new)
    await db.system_state.update_one({"id": KEY}, {"$set": {"inode": ino, "offset": offset, "synced_at": now_iso()}}, upsert=True)
    return {"enabled": True, "updated": n}


async def loop():
    await db.email_log.create_index("at")
    await db.email_log.create_index("message_id")
    await db.email_log.create_index("queue_id")
    await db.email_log.update_many({"status": {"$exists": False}}, {"$set": {"status": "logged", "kind": "other"}})
    while True:
        try:
            await sync()
        except Exception:
            logger.exception("mail log sync failed")
        await asyncio.sleep(120)


@router.get("")
async def list_log(q: str = "", kind: str = "", status: str = "", skip: int = 0, limit: int = 50, user=Depends(platform_admin)):
    f = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        f["$or"] = [{"to": rx}, {"subject": rx}]
    if kind in KINDS:
        f["kind"] = kind
    base = dict(f)
    if status in STATUSES:
        f["status"] = status
    limit = max(1, min(limit, 200))
    items = await db.email_log.find(f, {"_id": 0}).sort("at", -1).skip(max(0, skip)).limit(limit).to_list(limit)
    counts = {x["_id"]: x["n"] async for x in db.email_log.aggregate([{"$match": base}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    s = await db.system_state.find_one({"id": KEY}, {"_id": 0, "synced_at": 1}) or {}
    return {"items": items, "total": await db.email_log.count_documents(f), "counts": counts,
            "tracking": bool(MAIL_LOG_PATH), "synced_at": s.get("synced_at")}


@router.post("/sync")
async def run_sync(user=Depends(platform_admin)):
    return await sync()
