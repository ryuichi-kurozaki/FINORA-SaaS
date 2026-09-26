"""Japanese mutual funds: official 投資信託協会 library (search/NAV) + Yahoo!ファイナンス for 協会コード → name."""
import asyncio
import json
import re
import time
import unicodedata

import httpx

API = "https://toushin-lib.fwg.ne.jp/FdsWeb/FDST999900/fundDataSearch"
YJ = "https://finance.yahoo.co.jp/quote/{}"
ISIN_RE, CODE_RE = re.compile(r"JP[0-9A-Z]{10}"), re.compile(r"[0-9]{4}[0-9A-Z]{3}[0-9A-Z]")
ARRAYS = ("s_investAssetKindCd", "s_investArea3kindCd", "s_instCd", "s_fdsInstCd", "s_dcFundCD", "t_investArea10kindCd", "t_investAssetKindCd",
          "t_instCd", "t_fdsInstCd", "s_investArea10kindCd", "s_setlFqcy", "s_dividend1y", "s_totalNetAssets", "s_nowToRedemptionDate",
          "s_establishedDateToNow", "s_isinCd")
BASE = {"s_kensakuKbn": "1", "s_supplementKindCd": "1", "f_etfKBun": "1", "s_standardPriceCond1": "0", "s_standardPriceCond2": "0",
        "s_riskCond1": "0", "s_riskCond2": "0", "s_sharpCond1": "0", "s_sharpCond2": "0", "s_buyFee": "1", "s_trustReward": "1",
        "s_monthlyCancelCreateVal": "1", "salesInstDiv": "", "startNo": 0, "draw": 1, "searchBtnClickFlg": True}
_CACHE, TTL = {}, 600


def is_fund_code(t):
    return bool(ISIN_RE.fullmatch(t) or CODE_RE.fullmatch(t))


def _wide(s):
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)


def _item(x):
    price = float(x["standardPrice"]) if x.get("standardPrice") else None
    return {"ticker": x["associFundCd"], "isin": x["isinCd"], "name": unicodedata.normalize("NFKC", x.get("fundStNm") or x.get("fundNm") or ""),
            "exchange": x.get("entrustCmpNm") and unicodedata.normalize("NFKC", x["entrustCmpNm"])[:14], "asset_class": "fund", "country": "JP",
            "currency": "JPY", "price_unit": 10000, "price": price, "price_date": (x.get("standardDate") or "")[:10] or None, "source": "toushin"}


async def _official(keyword="", isin=None, limit=8):
    body = {**BASE, **{k: [] for k in ARRAYS}, "s_keyword": keyword, "s_isinCd": [isin] if isin else []}
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post(API, content=json.dumps(body), headers={"Content-Type": "application/json"})
    rows = ((r.json().get("searchResultInfo") or {}).get("resultInfoMapList")) or []
    return [_item(x) for x in rows[:limit] if x.get("associFundCd") and x.get("isinCd")]


async def _yahoo_name(code):
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as h:
        html = (await h.get(YJ.format(code))).text
    m = re.search(r"<title>(.*?)【", html)
    return m.group(1).strip() if m else None


async def resolve(t):
    """ISIN or 協会コード → official fund item (with latest NAV) or None."""
    hit = _CACHE.get(t)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    item = None
    if ISIN_RE.fullmatch(t):
        item = next(iter(await _official(isin=t, limit=1)), None)
    elif (name := await _yahoo_name(t)):
        words = re.split(r"[\s<>＜＞()（）]+", unicodedata.normalize("NFKC", name))
        for kw in (" ".join(w for w in words if w)[:40], " ".join(w for w in words if w)[:20]):
            item = next((x for x in await _official(_wide(kw), limit=40) if x["ticker"] == t), None)
            if item:
                break
    _CACHE[t] = (time.time(), item)
    return item


async def _yahoo_search(q, limit):
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as h:
        html = (await h.get("https://finance.yahoo.co.jp/search/", params={"query": q})).text
    m = re.search(r"__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    rows = (json.loads(m.group(1)).get("mainSearchList") or {}).get("results") or [] if m else []
    out = []
    for x in rows:
        if x.get("marketName") != "投資信託" or not CODE_RE.fullmatch(x.get("code") or ""):
            continue
        p = (x.get("price") or "").replace(",", "")
        out.append({"ticker": x["code"], "name": x.get("name") or x["code"], "exchange": "投信", "asset_class": "fund", "country": "JP",
                    "currency": "JPY", "price_unit": 10000, "price": float(p) if re.fullmatch(r"[\d.]+", p) else None, "source": "yahoo_jp"})
    return out[:limit]


async def search(q, limit=6):
    t = q.strip().upper()
    try:
        if is_fund_code(t):
            item = await asyncio.wait_for(resolve(t), 20)
            return [item] if item else []
        if len(q.strip()) < 2:
            return []
        res = await asyncio.wait_for(_official(_wide(q.strip()), limit=limit), 12)
        if not res and re.search(r"[A-Za-z]", q):
            res = await asyncio.wait_for(_yahoo_search(q.strip(), limit), 12)
        return res
    except Exception:  # noqa: BLE001
        return []
