"""Auto-link imported fund names to 協会コード and refresh current_price daily (6:00 JST) or on demand."""
import asyncio
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

import fund
import quote as quote_mod
from core import db, now_iso, current

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assets/prices")
JST = timezone(timedelta(hours=9))
RUN_HOUR = 6
MIN_RATIO = 0.74
_NOISE = re.compile(r"[\s　・/／\-－‐（）()＜＞<>\[\]「」【】,，.。]+")
_SUFFIX = re.compile(r"(ファンド|投信|愛称[:：].*|年\d+月決算型|\(.*?\))$")


def _norm(s):
    s = unicodedata.normalize("NFKC", s or "").upper()
    return _NOISE.sub("", s)


def _prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


async def match_ticker(name):
    """Fund name (as printed on a brokerage CSV) → 協会コード, or None when no confident match."""
    target = _norm(name)
    if len(target) < 3:
        return None
    seen = {}
    for cut in (24, 16, 10):
        kw = unicodedata.normalize("NFKC", name or "").strip()[:cut].strip()
        if not kw:
            continue
        try:
            rows = await asyncio.wait_for(fund._official(fund._wide(kw), limit=40), 15)
        except Exception:  # noqa: BLE001
            rows = []
        for r in rows:
            seen[r["ticker"]] = r
        if not rows:
            continue
        best, ratio = None, 0.0
        for r in seen.values():
            cand = _norm(r["name"])
            sc = SequenceMatcher(None, target, cand).ratio()
            pre = _prefix_len(target, cand)
            if cand and (pre >= 8 or pre >= 0.6 * min(len(target), len(cand))):
                sc = max(sc, 0.95)
            if sc > ratio:
                best, ratio = r, sc
        if best and ratio >= MIN_RATIO:
            return best["ticker"]
    return None


async def fetch_price(ticker, name=None):
    """→ (price, price_date) for a 協会コード / ISIN / listed ticker, else (None, None)."""
    t = (ticker or "").strip().upper()
    if not t:
        return None, None
    if fund.is_fund_code(t) or re.fullmatch(r"[0-9][0-9A-Z]{7}", t):
        try:
            f = await asyncio.wait_for(fund.resolve(t), 25)
        except Exception:  # noqa: BLE001
            f = None
        if not (f and f.get("price")) and name:
            f = await _by_name(t, name)
        if f and f.get("price"):
            return float(f["price"]), f.get("price_date") or date.today().isoformat()
        return None, None
    sym = t + ".T" if re.fullmatch(r"[0-9][0-9A-Z]{3}", t) else t
    if not re.fullmatch(r"[A-Z0-9.\-^=]{1,20}", sym):
        return None, None
    try:
        q = await asyncio.wait_for(asyncio.to_thread(quote_mod._fetch, sym), 25)
    except Exception:  # noqa: BLE001
        q = None
    if q and q.get("price"):
        return float(q["price"]), date.today().isoformat()
    return None, None


async def _by_name(ticker, name):
    """Codes are not searchable on the 投資信託協会 API, so re-find the fund row by its stored name."""
    base = unicodedata.normalize("NFKC", name or "").strip()
    for kw in (base[:24], _SUFFIX.sub("", base)[:24], base[:12]):
        kw = kw.strip()
        if not kw:
            continue
        try:
            rows = await asyncio.wait_for(fund._official(fund._wide(kw), limit=40), 15)
        except Exception:  # noqa: BLE001
            continue
        hit = next((r for r in rows if r["ticker"] == ticker), None)
        if hit:
            return hit
    return None


async def sync(tenant_id=None, client_id=None, link=True):
    """Link missing tickers by fund name, then refresh prices. Returns counters."""
    q = {"asset_class": {"$in": ["fund", "jp_stock", "foreign_stock", "etf"]}}
    if tenant_id:
        q["tenant_id"] = tenant_id
    if client_id:
        q["client_id"] = client_id
    assets = await db.assets.find(q).to_list(5000)
    linked = updated = skipped = failed = 0
    cache = {}
    for a in assets:
        tk = (a.get("ticker") or "").strip()
        if not tk and link and a.get("asset_class") == "fund" and a.get("name"):
            key = _norm(a["name"])
            if key not in cache:
                cache[key] = await match_ticker(a["name"])
            tk = cache[key] or ""
            if tk:
                await db.assets.update_one({"id": a["id"]}, {"$set": {"ticker": tk, "updated_at": now_iso()}})
                linked += 1
        if not tk:
            continue
        price, pdate = await fetch_price(tk, a.get("name"))
        if not price:
            failed += 1
            continue
        cur = a.get("current_price") or 0
        if cur and not 0.1 <= price / cur <= 10:
            skipped += 1
            continue
        if cur == price and a.get("price_date") == pdate:
            continue
        await db.assets.update_one({"id": a["id"]}, {"$set": {"current_price": round(price, 4), "price_date": pdate, "updated_at": now_iso()}})
        updated += 1
    return {"assets": len(assets), "linked": linked, "updated": updated, "skipped": skipped, "failed": failed}


async def loop():
    """Daily refresh at 06:00 JST (previous business day's NAV is published by then)."""
    while True:
        now = datetime.now(JST)
        nxt = now.replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        await asyncio.sleep((nxt - now).total_seconds())
        try:
            res = await sync()
            logger.info("daily price sync: %s", res)
        except Exception:
            logger.exception("daily price sync failed")


@router.post("/sync")
async def sync_now(client_id: Optional[str] = None, user=Depends(current)):
    if user["role"] == "client":
        client_id = user.get("client_id")
    elif not client_id:
        raise HTTPException(422, "Select a client before refreshing prices")
    else:
        c = await db.clients.find_one({"id": client_id, "tenant_id": user["tenant_id"]}, {"consultant_id": 1})
        if not c:
            raise HTTPException(404, "Client not found")
        if user["role"] == "consultant" and c.get("consultant_id") != user["id"]:
            raise HTTPException(403, "No access to this client")
    return await sync(user["tenant_id"], client_id)
