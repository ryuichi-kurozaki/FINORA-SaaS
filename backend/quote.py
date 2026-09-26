"""Ticker quote lookup (Yahoo Finance via yfinance, no API key) used to prefill asset entry forms."""
import asyncio
import re
import time
from datetime import date

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException

from core import current

router = APIRouter(prefix="/api")
_CACHE, TTL = {}, 600
SUFFIX_COUNTRY = {"T": "JP", "SA": "BR"}


def _fetch(t):
    tk = yf.Ticker(t)
    fi = tk.fast_info
    price = fi.last_price
    if not price:
        return None
    try:
        info = tk.info or {}
    except Exception:  # noqa: BLE001
        info = {}
    suffix = t.rsplit(".", 1)[1] if "." in t else ""
    return {"ticker": t, "name": info.get("longName") or info.get("shortName") or t, "price": round(float(price), 4),
            "currency": fi.currency or info.get("currency"), "country": SUFFIX_COUNTRY.get(suffix, "US" if not suffix else "other")}


@router.get("/quote")
async def quote(ticker: str, user=Depends(current)):
    t = ticker.strip().upper()[:20]
    if not re.fullmatch(r"[A-Z0-9.\-^=]{1,20}", t):
        raise HTTPException(422, "Invalid ticker")
    hit = _CACHE.get(t)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        q = await asyncio.wait_for(asyncio.to_thread(_fetch, t), 20)
    except Exception:  # noqa: BLE001
        q = None
    if not q:
        raise HTTPException(404, "Quote not found for this ticker")
    q["price_date"] = date.today().isoformat()
    _CACHE[t] = (time.time(), q)
    return q
