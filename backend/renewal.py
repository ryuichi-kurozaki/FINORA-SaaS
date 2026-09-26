"""Renewal/expiry reminders for ACTIVE e-contracts: 30 and 7 days before, to both parties (in-app + email + WhatsApp)."""
import asyncio
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from core import db, new_id, now_iso, current, notify
from econtract import renew_on, _people
from sign_notify import send_renewal_notice

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/econtracts/renewals")
STAGES = (7, 30)


async def _send(c, rd, days):
    params = {"label": f"{c['number']} {c['terms']['service_name']} ({rd})", "date": rd, "days": days,
              "auto_renew": bool(c["terms"].get("auto_renew")), "contract_type": c["contract_type"]}
    for tid, uid in await _people(c, "ISSUER") + await _people(c, "RECIPIENT"):
        if not uid:
            continue
        await notify(tid, [uid], "econtract_renewal_notice", params, c.get("client_id"), f"/econtracts/{c['id']}")
        await send_renewal_notice(uid, c, rd, days)


async def scan(today=None):
    t, sent = today or date.today(), []
    async for c in db.econtracts.find({"status": "ACTIVE"}):
        rd = renew_on(c, t)
        days = (rd - t).days if rd else None
        stage = next((s for s in STAGES if days is not None and days <= s), None)
        if stage is None:
            continue
        key = f"{c['id']}:{rd.isoformat()}:{stage}"
        try:
            await db.renewal_notices.insert_one({"id": new_id(), "key": key, "contract_id": c["id"], "tenant_id": c["tenant_id"],
                                                 "renew_on": rd.isoformat(), "stage": stage, "days": days, "at": now_iso()})
        except DuplicateKeyError:
            continue
        await _send(c, rd.isoformat(), days)
        sent.append({"contract_id": c["id"], "number": c["number"], "renew_on": rd.isoformat(), "stage": stage, "days": days})
    return sent


async def loop():
    await db.renewal_notices.create_index("key", unique=True)
    while True:
        try:
            sent = await scan()
            if sent:
                logger.info("renewal notices sent: %s", len(sent))
        except Exception:
            logger.exception("renewal scan failed")
        await asyncio.sleep(3600)


@router.post("/run")
async def run(today: Optional[str] = None, user=Depends(current)):
    if not user.get("platform_admin"):
        raise HTTPException(403, "Forbidden")
    return {"sent": await scan(date.fromisoformat(today) if today else None)}
