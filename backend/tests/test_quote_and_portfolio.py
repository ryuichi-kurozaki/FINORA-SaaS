"""Tests for /api/quote (yfinance-backed) and client-owned assets flow on /portfolio."""
import os
import time
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login(email, pw="Finora2026!"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.cookies


def _s(cookies, lang="ja"):
    s = requests.Session()
    s.cookies.update(cookies)
    s.headers.update({"X-Lang": lang, "Content-Type": "application/json"})
    return s


# ---------- /api/quote ----------
def test_quote_unauthenticated_401():
    r = requests.get(f"{BASE}/api/quote", params={"ticker": "AAPL"}, timeout=10)
    assert r.status_code == 401


def test_quote_invalid_ticker_422_ja():
    s = _s(_login("client@finora.co.jp"), "ja")
    r = s.get(f"{BASE}/api/quote", params={"ticker": "!!!"})
    assert r.status_code == 422, r.text
    assert "銘柄コード" in r.json().get("detail", "")


def test_quote_unknown_ticker_404_ja():
    s = _s(_login("client@finora.co.jp"), "ja")
    r = s.get(f"{BASE}/api/quote", params={"ticker": "ZZZZZZZZ9"}, timeout=30)
    assert r.status_code == 404
    assert "銘柄コード" in r.json().get("detail", "")


def test_quote_aapl_ok():
    s = _s(_login("client@finora.co.jp"), "ja")
    r = s.get(f"{BASE}/api/quote", params={"ticker": "AAPL"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("ticker", "name", "price", "currency", "country", "price_date"):
        assert k in d, f"missing {k}"
    assert d["ticker"] == "AAPL"
    assert d["country"] == "US"
    assert isinstance(d["price"], (int, float)) and d["price"] > 0


def test_quote_jp_ticker():
    s = _s(_login("client@finora.co.jp"), "ja")
    r = s.get(f"{BASE}/api/quote", params={"ticker": "7203.T"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["country"] == "JP"
    assert d["currency"] in ("JPY", None) or d["currency"]


def test_quote_br_ticker():
    s = _s(_login("client@finora.co.jp"), "ja")
    r = s.get(f"{BASE}/api/quote", params={"ticker": "PETR4.SA"}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["country"] == "BR"


# ---------- Client can add/edit/delete own asset ----------
def test_client_owned_asset_crud_and_notification():
    # Login as client and consultant
    client_s = _s(_login("client@finora.co.jp"), "ja")
    consultant_s = _s(_login("consultant@finora.co.jp"), "ja")

    me = client_s.get(f"{BASE}/api/auth/me").json()
    client_id = me.get("client_id")
    assert client_id, f"client user missing client_id: {me}"

    # Baseline consultant notifications
    n0 = consultant_s.get(f"{BASE}/api/notifications").json().get("items", [])
    n0_ids = {n["id"] for n in n0}

    # CREATE
    payload = {
        "client_id": client_id,
        "asset_class": "foreign_stock",
        "name": "TEST_QA_Apple",
        "ticker": "AAPL",
        "currency": "USD",
        "country": "US",
        "quantity": 10,
        "current_price": 200,
    }
    r = client_s.post(f"{BASE}/api/data/assets", json=payload)
    assert r.status_code in (200, 201), r.text
    asset = r.json()
    aid = asset["id"]
    assert asset["name"] == "TEST_QA_Apple"
    assert asset["client_id"] == client_id

    # GET verify persistence
    r = client_s.get(f"{BASE}/api/data/assets")
    assert any(a["id"] == aid for a in r.json())

    # UPDATE
    r = client_s.put(f"{BASE}/api/data/assets/{aid}", json={**payload, "name": "TEST_QA_Apple2", "quantity": 15})
    assert r.status_code in (200, 204), r.text
    r = client_s.get(f"{BASE}/api/data/assets")
    upd = next(a for a in r.json() if a["id"] == aid)
    assert upd["name"] == "TEST_QA_Apple2"
    assert upd["quantity"] == 15

    # NOTIFICATION check
    time.sleep(1)
    n1 = consultant_s.get(f"{BASE}/api/notifications").json().get("items", [])
    new = [n for n in n1 if n["id"] not in n0_ids]
    kinds = {n.get("kind") or n.get("type") for n in new}
    assert "client_data_updated" in kinds, f"Expected client_data_updated in {kinds}"

    # DELETE
    r = client_s.delete(f"{BASE}/api/data/assets/{aid}")
    assert r.status_code in (200, 204)
    r = client_s.get(f"{BASE}/api/data/assets")
    assert not any(a["id"] == aid for a in r.json())


def test_staff_read_only_on_client_owned_asset():
    """Staff cannot create/edit an asset owned by a client via /data/assets on that client."""
    client_s = _s(_login("client@finora.co.jp"), "ja")
    me = client_s.get(f"{BASE}/api/auth/me").json()
    cid = me["client_id"]
    # Client creates
    r = client_s.post(f"{BASE}/api/data/assets", json={
        "client_id": cid, "asset_class": "cash", "name": "TEST_QA_ClientOwned",
        "currency": "JPY", "quantity": 1, "current_price": 100,
    })
    assert r.status_code in (200, 201), r.text
    aid = r.json()["id"]

    consultant_s = _s(_login("consultant@finora.co.jp"), "ja")
    r = consultant_s.put(f"{BASE}/api/data/assets/{aid}", json={"name": "STAFF_TRY_MODIFY"})
    # Expect forbidden/read-only enforcement
    assert r.status_code in (403, 400, 409), f"expected block, got {r.status_code}: {r.text}"

    # Cleanup
    client_s.delete(f"{BASE}/api/data/assets/{aid}")
