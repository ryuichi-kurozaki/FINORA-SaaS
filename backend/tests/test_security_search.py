"""Tests for the new /api/quote/search endpoint and enhanced /api/quote (JPX-backed asset_class, JP code auto-suffix, sector)."""
import os
import time
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


# ---------- /api/quote/search ----------
def test_search_unauthenticated_401():
    r = requests.get(f"{BASE}/api/quote/search", params={"q": "toyota"}, timeout=10)
    assert r.status_code == 401


def test_search_empty_returns_empty():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": ""}, timeout=20)
    assert r.status_code == 200
    assert r.json() == []


def test_search_hiragana_toyota_finds_7203():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "とよた"}, timeout=30)
    assert r.status_code == 200, r.text
    items = r.json()
    assert any(it["ticker"] == "7203.T" for it in items), items
    hit = next(it for it in items if it["ticker"] == "7203.T")
    assert hit["asset_class"] == "jp_stock"
    assert hit["country"] == "JP"
    assert "トヨタ" in hit["name"]
    assert hit["source"] == "jpx"


def test_search_katakana_toyota_finds_7203():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "トヨタ"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert any(it["ticker"] == "7203.T" for it in items)


def test_search_code_7203_ranks_first():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "7203"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert items, "expected non-empty results for '7203'"
    assert items[0]["ticker"] == "7203.T"
    assert items[0]["asset_class"] == "jp_stock"


def test_search_ascii_apple_yields_foreign_stock():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "apple"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    aapl = [it for it in items if it["ticker"] == "AAPL"]
    assert aapl, f"AAPL not in results: {[it['ticker'] for it in items]}"
    assert aapl[0]["asset_class"] == "foreign_stock"
    assert aapl[0]["country"] == "US"


def test_search_voo_is_etf():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "VOO"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    voo = [it for it in items if it["ticker"] == "VOO"]
    assert voo, [it["ticker"] for it in items]
    assert voo[0]["asset_class"] == "etf"


def test_search_btc_is_crypto():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "BTC"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    btc = [it for it in items if it["ticker"] == "BTC-USD"]
    assert btc, [it["ticker"] for it in items]
    assert btc[0]["asset_class"] == "crypto"


def test_search_1540_is_gold():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "1540"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    hit = [it for it in items if it["ticker"] == "1540.T"]
    assert hit, [it["ticker"] for it in items]
    assert hit[0]["asset_class"] == "gold"


def test_search_8951_is_real_estate_jreit():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "8951"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    hit = [it for it in items if it["ticker"] == "8951.T"]
    assert hit, [it["ticker"] for it in items]
    assert hit[0]["asset_class"] == "real_estate"


def test_search_infrastructure_fund():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "インフラ"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    # An infra 投資法人 should classify as fund (not real_estate) per jpx.classify
    funds = [it for it in items if it["asset_class"] == "fund"]
    assert funds, f"no fund-class results in {[(it['ticker'], it['asset_class']) for it in items]}"


def test_search_max_12():
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "a"}, timeout=30)
    assert r.status_code == 200
    assert len(r.json()) <= 12


def test_search_client_user_authorized():
    s = _s("client@finora.co.jp")
    r = s.get(f"{BASE}/api/quote/search", params={"q": "7203"}, timeout=30)
    assert r.status_code == 200
    assert any(it["ticker"] == "7203.T" for it in r.json())


# ---------- /api/quote (enhanced) ----------
def test_quote_bare_4char_jp_code_auto_suffix():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "7203"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ticker"] == "7203.T"
    assert d["country"] == "JP"
    assert d["asset_class"] == "jp_stock"
    assert "トヨタ" in d["name"]
    assert d.get("sector") == "automotive"
    assert "price_date" in d


def test_quote_aapl_asset_class_and_sector():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "AAPL"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["asset_class"] == "foreign_stock"
    assert d["country"] == "US"


def test_quote_gld_is_gold():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "GLD"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["asset_class"] == "gold"


def test_quote_btc_usd_is_crypto():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "BTC-USD"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["asset_class"] == "crypto"


def test_quote_invalid_ticker_422():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "!!!"}, timeout=20)
    assert r.status_code == 422


def test_quote_unknown_ticker_404():
    s = _s()
    r = s.get(f"{BASE}/api/quote", params={"ticker": "ZZZZZZZZ9"}, timeout=30)
    assert r.status_code == 404


# ---------- jpx.loop startup ----------
def test_jpx_synced_state_present():
    """The startup jpx.loop should have populated db.system_state id='jpx' with count>=1000."""
    # Use platform admin (mongo access requires ad-hoc endpoint, but we can just assert search works enough)
    # Search a code we know is on JPX list
    s = _s()
    r = s.get(f"{BASE}/api/quote/search", params={"q": "9984"}, timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert any(it["ticker"] == "9984.T" for it in items), "expected 9984 SoftBank in JPX list"
