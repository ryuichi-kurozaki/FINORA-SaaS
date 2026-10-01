"""Auto-link imported fund names to 協会コード and refresh current_price daily (6:00 JST) or on demand."""
import asyncio
import logging
import re
import time
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
MIN_RATIO = 0.85
MIN_MARGIN = 0.04
_NOISE = re.compile(r"[\s　・/／\-－‐（）()＜＞<>\[\]「」【】,，.。]+")
_ALIAS = re.compile(r"《.*?》|〈.*?〉|【.*?】|愛称[:：].*$")
_SUFFIX = re.compile(r"(ファンド|投信|愛称[:：].*|年\d+月決算型|\(.*?\))$")
CYCLES = ("毎月分配", "毎月決算", "隔月分配", "隔月決算", "奇数月決算", "偶数月決算", "年2回決算", "年4回決算", "年1回決算", "1年決算", "3ヶ月決算")


def _norm(s):
    s = unicodedata.normalize("NFKC", s or "").upper()
    s = _ALIAS.sub("", s).replace("ファンド", "F")
    return _NOISE.sub("", s)


def _cycle(s):
    """決算・分配周期タグ（毎月分配型/年2回決算型など）。シリーズ違いの誤ひも付けを防ぐための必須一致キー。"""
    n = _NOISE.sub("", unicodedata.normalize("NFKC", s or ""))
    return next((c for c in CYCLES if c in n), "")


def _prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


async def match_ticker(name):
    """Fund name (as printed on a brokerage CSV) → 協会コード, or None when no confident match.
    Strict by design: the 決算周期 must match and the runner-up must be clearly worse, otherwise we leave it for manual linking."""
    target, tcycle = _norm(name), _cycle(name)
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
        scored = []
        for r in seen.values():
            if _cycle(r["name"]) != tcycle:
                continue
            cand = _norm(r["name"])
            if not cand:
                continue
            sc = SequenceMatcher(None, target, cand).ratio()
            pre = _prefix_len(target, cand)
            if pre >= 10 and pre >= 0.8 * min(len(target), len(cand)):
                sc = max(sc, 0.95)
            scored.append((sc, r["ticker"]))
        scored.sort(reverse=True)
        if scored and scored[0][0] >= MIN_RATIO and (len(scored) == 1 or scored[0][0] - scored[1][0] >= MIN_MARGIN):
            return scored[0][1]
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
    linked = updated = skipped = failed = unmatched = 0
    cache = {}
    for a in assets:
        tk = (a.get("ticker") or "").strip()
        new_link = False
        if not tk and link and a.get("asset_class") == "fund" and a.get("name"):
            key = _norm(a["name"])
            if key not in cache:
                cache[key] = await match_ticker(a["name"])
            tk = cache[key] or ""
            new_link = bool(tk)
        if not tk:
            continue
        price, pdate = await fetch_price(tk, a.get("name"))
        if not price:
            failed += 1
            continue
        cur = a.get("current_price") or 0
        if new_link:
            # A wrong same-family match shows up as a NAV far from the imported one: leave it unlinked for manual review.
            if cur and not 0.5 <= price / cur <= 2:
                unmatched += 1
                continue
            await db.assets.update_one({"id": a["id"]}, {"$set": {"ticker": tk, "updated_at": now_iso()}})
            linked += 1
        if cur and not 0.1 <= price / cur <= 10:
            skipped += 1
            continue
        if cur == price and a.get("price_date") == pdate:
            continue
        await db.assets.update_one({"id": a["id"]}, {"$set": {"current_price": round(price, 4), "price_date": pdate, "updated_at": now_iso()}})
        updated += 1
    return {"assets": len(assets), "linked": linked, "updated": updated, "skipped": skipped, "failed": failed, "unmatched": unmatched}


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


LINKABLE = ["fund", "jp_stock", "foreign_stock", "etf"]


async def _scoped(user, client_id):
    """Resolve the client scope for a price action, raising when the caller has no access."""
    if user["role"] == "client":
        return user.get("client_id")
    if client_id:
        c = await db.clients.find_one({"id": client_id, "tenant_id": user["tenant_id"]}, {"consultant_id": 1})
        if not c:
            raise HTTPException(404, "Client not found")
        if user["role"] == "consultant" and c.get("consultant_id") != user["id"]:
            raise HTTPException(403, "No access to this client")
        return client_id
    if user["role"] == "consultant":
        raise HTTPException(422, "Select a client before refreshing prices")
    return None


@router.get("/unlinked")
async def unlinked(client_id: Optional[str] = None, user=Depends(current)):
    """Assets whose 協会コード/ティッカー could not be matched automatically — shown for manual linking."""
    cid = await _scoped(user, client_id)
    q = {"tenant_id": user["tenant_id"], "asset_class": {"$in": LINKABLE}, "$or": [{"ticker": None}, {"ticker": ""}, {"ticker": {"$exists": False}}]}
    if cid:
        q["client_id"] = cid
    rows = await db.assets.find(q, {"_id": 0, "id": 1, "name": 1, "asset_class": 1, "client_id": 1, "currency": 1,
                                    "current_price": 1, "quantity": 1, "account_id": 1}).to_list(500)
    names = {c["id"]: c.get("corporate_name") or c.get("name")
             for c in await db.clients.find({"tenant_id": user["tenant_id"]}, {"id": 1, "name": 1, "corporate_name": 1}).to_list(5000)}
    for r in rows:
        r["client_name"] = names.get(r.get("client_id"))
    return rows


@router.post("/link")
async def link(asset_id: str, ticker: str, user=Depends(current)):
    tk = (ticker or "").strip().upper()[:20]
    if not tk:
        raise HTTPException(422, "Ticker required")
    a = await db.assets.find_one({"id": asset_id, "tenant_id": user["tenant_id"]})
    if not a:
        raise HTTPException(404, "Asset not found")
    await _scoped(user, a.get("client_id"))
    upd = {"ticker": tk, "updated_at": now_iso()}
    price, pdate = await fetch_price(tk, a.get("name"))
    if price:
        upd["current_price"], upd["price_date"] = round(price, 4), pdate
    await db.assets.update_one({"id": a["id"]}, {"$set": upd})
    return {"id": a["id"], "ticker": tk, "current_price": upd.get("current_price"), "price_date": upd.get("price_date")}


_RUNNING = {}
_LAST = {}
MIN_GAP = 150


@router.post("/sync")
async def sync_now(client_id: Optional[str] = None, user=Depends(current)):
    if user["role"] == "client":
        client_id = user.get("client_id")
    elif client_id:
        c = await db.clients.find_one({"id": client_id, "tenant_id": user["tenant_id"]}, {"consultant_id": 1})
        if not c:
            raise HTTPException(404, "Client not found")
        if user["role"] == "consultant" and c.get("consultant_id") != user["id"]:
            raise HTTPException(403, "No access to this client")
    elif user["role"] == "consultant":
        raise HTTPException(422, "Select a client before refreshing prices")
    key = f"{user['tenant_id']}:{client_id or ''}"
    cached = _LAST.get(key)
    if _RUNNING.get(key) or (cached and time.time() - cached[0] < MIN_GAP):
        return {**(cached[1] if cached else {"assets": 0, "linked": 0, "updated": 0, "skipped": 0, "failed": 0}), "cached": True}
    _RUNNING[key] = True
    try:
        res = await sync(user["tenant_id"], client_id)
    finally:
        _RUNNING.pop(key, None)
    _LAST[key] = (time.time(), res)
    return res
