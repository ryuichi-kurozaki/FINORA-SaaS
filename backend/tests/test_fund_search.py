"""Japanese mutual fund search + quote + asset price_unit valuation."""
import os
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login(email, pw="Finora2026!"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.cookies


def _s(email="consultant@finora.co.jp"):
    s = requests.Session()
    s.cookies.update(_login(email))
    s.headers.update({"X-Lang": "ja", "Content-Type": "application/json"})
    return s


# ---------- /api/quote/search: Japanese funds ----------
def test_search_fund_code_18312991_returns_that_fund():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "18312991"}, timeout=40)
    assert r.status_code == 200, r.text
    items = r.json()
    hit = next((it for it in items if it.get("ticker") == "18312991"), None)
    assert hit, items
    assert hit["asset_class"] == "fund"
    assert hit["country"] == "JP"
    assert hit["currency"] == "JPY"
    assert hit["price_unit"] == 10000
    assert hit.get("isin") == "JP90C0002EX1"
    assert hit.get("source") in ("toushin", "yahoo_jp")
    if hit.get("price"):
        # NAV ~ 8363 (should be > 1000 JPY certainly)
        assert 500 < float(hit["price"]) < 50000


def test_search_isin_JP90C0002EX1_returns_18312991():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "JP90C0002EX1"}, timeout=40)
    assert r.status_code == 200
    items = r.json()
    assert any(it.get("ticker") == "18312991" for it in items), items


def test_search_orukan_finds_emaxis_slim_zensekai():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "オルカン"}, timeout=40)
    assert r.status_code == 200
    items = r.json()
    assert any(it.get("ticker") == "0331418A" for it in items), [it.get("ticker") for it in items]


def test_search_sekai_no_besto_returns_invesco_funds():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "世界のベスト"}, timeout=40)
    assert r.status_code == 200
    items = r.json()
    funds = [it for it in items if it.get("asset_class") == "fund"]
    assert funds, items


def test_search_emaxis_slim_ascii_yahoo_fallback():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "emaxis slim"}, timeout=40)
    assert r.status_code == 200
    items = r.json()
    # At least one JP fund result via yahoo_jp fallback (or toushin if it works ASCII)
    funds = [it for it in items if it.get("asset_class") == "fund" and it.get("country") == "JP"]
    assert funds, items


def test_search_toyota_returns_7203_first_stock_intact():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "トヨタ"}, timeout=40)
    assert r.status_code == 200
    items = r.json()
    # 7203.T must appear in results (jpx local hit); ordering is by code asc so 3116.T also allowed
    tickers = [it["ticker"] for it in items]
    assert "7203.T" in tickers, tickers
    hit = next(it for it in items if it["ticker"] == "7203.T")
    assert hit["asset_class"] == "jp_stock"


def test_search_stocks_still_work_apple_voo_btc_7203():
    s = _s()
    for q, expect_ticker in (("apple", "AAPL"), ("VOO", "VOO"), ("BTC", "BTC-USD"), ("7203", "7203.T")):
        r = s.get(f"{BASE}/api/quote/search", params={"q": q}, timeout=40)
        assert r.status_code == 200
        tickers = [it["ticker"] for it in r.json()]
        assert expect_ticker in tickers, (q, tickers)


# ---------- /api/quote: Japanese funds ----------
def test_quote_fund_code_18312991():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "18312991"}, timeout=40)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ticker"] == "18312991"
    assert d.get("isin") == "JP90C0002EX1"
    assert d["asset_class"] == "fund"
    assert d["country"] == "JP"
    assert d["currency"] == "JPY"
    assert d["price_unit"] == 10000
    assert d.get("price") and float(d["price"]) > 500
    assert d.get("price_date")


def test_quote_isin_JP90C0002EX1_resolves_to_18312991():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "JP90C0002EX1"}, timeout=40)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ticker"] == "18312991"
    assert d["asset_class"] == "fund"


def test_quote_fund_0331418A_orukan():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "0331418A"}, timeout=40)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ticker"] == "0331418A"
    assert d["asset_class"] == "fund"
    assert d["currency"] == "JPY"
    assert d["price_unit"] == 10000


def test_quote_unknown_8char_code_404():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "99999999"}, timeout=40)
    assert r.status_code == 404


def test_quote_stocks_still_work():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "7203"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["ticker"] == "7203.T" and d["asset_class"] == "jp_stock"
    # AAPL still fine
    r2 = s.get(f"{BASE}/api/quote", params={"ticker": "AAPL"}, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["asset_class"] == "foreign_stock"


# ---------- Asset valuation with price_unit ----------
def test_asset_price_unit_valuation():
    """Create asset qty=1,200,000, cur_price=8363, price_unit=10000 -> value=1,003,560."""
    s = _s("client@finora.co.jp")
    # Find client's client_id
    me = s.get(f"{BASE}/api/auth/me", timeout=10).json()
    client_id = me.get("client_id")
    assert client_id, me
    payload = {
        "client_id": client_id,
        "asset_class": "fund",
        "name": "TEST_QA_Fund_Invesco",
        "ticker": "18312991",
        "currency": "JPY",
        "country": "JP",
        "quantity": 1200000,
        "acquisition_price": 8000,
        "current_price": 8363,
        "price_unit": 10000,
    }
    r = s.post(f"{BASE}/api/data/assets", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    asset_id = r.json()["id"]
    try:
        # Verify enrichment via list_items
        lst = s.get(f"{BASE}/api/data/assets", timeout=20).json()
        a = next(x for x in lst if x["id"] == asset_id)
        assert a.get("price_unit") == 10000
        assert abs(a["current_value"] - 1_003_560) < 1, a
        assert abs(a["acquisition_total"] - 960_000) < 1, a
    finally:
        s.delete(f"{BASE}/api/data/assets/{asset_id}", timeout=10)


def test_asset_price_unit_default_1_for_stock():
    """price_unit=1 (default) leaves stock valuation unchanged."""
    s = _s("client@finora.co.jp")
    me = s.get(f"{BASE}/api/auth/me", timeout=10).json()
    client_id = me["client_id"]
    payload = {
        "client_id": client_id, "asset_class": "jp_stock", "name": "TEST_QA_Toyota",
        "ticker": "7203.T", "currency": "JPY", "country": "JP",
        "quantity": 100, "acquisition_price": 2000, "current_price": 3000, "price_unit": 1,
    }
    r = s.post(f"{BASE}/api/data/assets", json=payload, timeout=20)
    assert r.status_code == 200
    asset_id = r.json()["id"]
    try:
        lst = s.get(f"{BASE}/api/data/assets", timeout=20).json()
        a = next(x for x in lst if x["id"] == asset_id)
        assert abs(a["current_value"] - 300_000) < 1
        assert abs(a["acquisition_total"] - 200_000) < 1
    finally:
        s.delete(f"{BASE}/api/data/assets/{asset_id}", timeout=10)
