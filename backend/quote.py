"""Ticker quote lookup + security search (Yahoo Finance via yfinance, JPX list for Japanese names) used to prefill asset entry."""
import asyncio
import re
import time
from datetime import date

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException

import fund
import jpx
from core import current

router = APIRouter(prefix="/api")
_CACHE, _SCACHE, TTL = {}, {}, 600
SUFFIX_COUNTRY = {"T": "JP", "SA": "BR"}
YTYPES = {"EQUITY", "ETF", "MUTUALFUND", "CRYPTOCURRENCY", "CURRENCY"}
YSECTOR = {"Technology": "technology", "Communication Services": "technology", "Financial Services": "finance", "Healthcare": "healthcare",
           "Energy": "energy", "Utilities": "energy", "Real Estate": "real_estate", "Consumer Cyclical": "consumer",
           "Consumer Defensive": "consumer", "Industrials": "industrial", "Basic Materials": "commodity"}


def _country(sym, qtype):
    if qtype in ("CRYPTOCURRENCY", "CURRENCY"):
        return "GLOBAL"
    suffix = sym.rsplit(".", 1)[1] if "." in sym else ""
    return SUFFIX_COUNTRY.get(suffix, "US" if not suffix else "other")


def _class(sym, qtype, name):
    n = (name or "").lower()
    if qtype == "EQUITY":
        return "jp_stock" if sym.endswith(".T") else "foreign_stock"
    if qtype == "ETF":
        return "gold" if "gold" in n else "precious_metal" if any(w in n for w in ("silver", "platinum", "palladium", "precious")) else "etf"
    return {"MUTUALFUND": "fund", "CRYPTOCURRENCY": "crypto", "CURRENCY": "fx"}.get(qtype, "other")


def _sector(sector, industry):
    return "automotive" if "Auto" in (industry or "") else YSECTOR.get(sector or "")


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
    name = info.get("longName") or info.get("shortName") or t
    qtype = info.get("quoteType") or "EQUITY"
    return {"ticker": t, "name": name, "price": round(float(price), 4), "currency": fi.currency or info.get("currency"),
            "country": _country(t, qtype), "asset_class": _class(t, qtype, name), "sector": _sector(info.get("sector"), info.get("industry"))}


def _ysearch(q):
    out = []
    for r in yf.Search(q, max_results=8, news_count=0).quotes:
        sym, qtype = r.get("symbol"), r.get("quoteType")
        if not sym or qtype not in YTYPES:
            continue
        name = r.get("longname") or r.get("shortname") or sym
        out.append({"ticker": sym, "name": name, "exchange": r.get("exchDisp") or r.get("exchange"), "asset_class": _class(sym, qtype, name),
                    "country": _country(sym, qtype), "sector": _sector(r.get("sector"), r.get("industry")), "source": "yahoo"})
    return out


@router.get("/quote/search")
async def search(q: str, user=Depends(current)):
    q = q.strip()[:40]
    if not q:
        return []
    hit = _SCACHE.get(q.lower())
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    local = await jpx.search(q)
    funds_task = asyncio.create_task(fund.search(q))
    remote = []
    if re.search(r"[A-Za-z0-9]", q) and not fund.is_fund_code(q.strip().upper()):
        try:
            remote = await asyncio.wait_for(asyncio.to_thread(_ysearch, q), 10)
        except Exception:  # noqa: BLE001
            remote = []
    funds = await funds_task
    seen = {x["ticker"] for x in local}
    res = (local[:6] + funds[:6] + [r for r in remote if r["ticker"] not in seen][:6])[:15]
    _SCACHE[q.lower()] = (time.time(), res)
    return res


@router.get("/quote")
async def quote(ticker: str, user=Depends(current)):
    t = ticker.strip().upper()[:20]
    if fund.is_fund_code(t):
        try:
            f = await asyncio.wait_for(fund.resolve(t), 20)
        except Exception:  # noqa: BLE001
            f = None
        if not f or not f.get("price"):
            raise HTTPException(404, "Quote not found for this ticker")
        return f
    if re.fullmatch(r"[0-9][0-9A-Z]{3}", t):
        t += ".T"
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
    if t.endswith(".T") and (jp := await jpx.get(t[:-2])):
        q.update({k: jp[k] for k in ("name", "asset_class", "sector") if jp.get(k)})
    q["price_date"] = date.today().isoformat()
    _CACHE[t] = (time.time(), q)
    return q
