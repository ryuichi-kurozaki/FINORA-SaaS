"""WhatsApp sender health: probe every 5 min; admin banner + email to platform admins on state change."""
import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends

from core import db, now_iso, require_roles
from email_service import send_email
from sign_notify import APP_URL, TXT, WA_URL, _html

router = APIRouter(prefix="/api/system")
logger = logging.getLogger(__name__)
KEY = "wa_health"
FAILS_TO_ALERT = 2
MAIL = {True: ("【FINORA】WhatsApp通知が復旧しました", "JWSEAのWhatsApp送信係との接続が復旧しました。WhatsApp通知は通常どおり送信されます。"),
        False: ("【FINORA】WhatsApp通知が停止しています", "JWSEAのWhatsApp送信係に接続できません（{detail}）。メール・アプリ内通知は通常どおり届きます。JWSEAサーバーの jwsea-wa サービス、配信専用番号のログイン状態、FINORAサーバーの finora-wa-tunnel を確認してください。")}


async def probe():
    try:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(f"{WA_URL}/status")
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        j = r.json()
        return bool(j.get("connected")), j.get("error") or ("" if j.get("connected") else "not connected")
    except Exception as e:  # noqa: BLE001
        return False, f"unreachable ({e.__class__.__name__})"


async def _mail(ok, detail):
    subject, body = MAIL[ok]
    async for u in db.users.find({"platform_admin": True, "active": {"$ne": False}}, {"email": 1, "name": 1}):
        try:
            await send_email(to=u["email"], subject=subject, html=_html({**TXT["ja"], "login": ""}, u.get("name") or u["email"], body.format(detail=detail), f"{APP_URL}/platform", "FINORAを開く"), kind="system")
        except Exception as e:  # noqa: BLE001
            logger.error("wa health mail failed: %s", e)


async def check():
    if not WA_URL:
        return None
    raw_ok, detail = await probe()
    prev = await db.system_state.find_one({"id": KEY}) or {}
    fails = 0 if raw_ok else prev.get("fails", 0) + 1
    ok = True if raw_ok else (False if fails >= FAILS_TO_ALERT else prev.get("ok", True))
    upd = {"ok": ok, "fails": fails, "detail": detail, "checked_at": now_iso()}
    if prev.get("ok") != ok:
        upd["since"] = now_iso()
        if not ok or prev.get("ok") is False:
            await _mail(ok, detail)
    await db.system_state.update_one({"id": KEY}, {"$set": upd}, upsert=True)
    return upd


async def loop():
    while True:
        try:
            await check()
        except Exception:
            logger.exception("wa health check failed")
        await asyncio.sleep(300)


@router.get("/wa-health")
async def wa_health(user=Depends(require_roles("admin"))):
    s = await db.system_state.find_one({"id": KEY}, {"_id": 0}) or {}
    return {"configured": bool(WA_URL), "ok": s.get("ok", True), "since": s.get("since"), "checked_at": s.get("checked_at"),
            "detail": s.get("detail") if user.get("platform_admin") else None}
