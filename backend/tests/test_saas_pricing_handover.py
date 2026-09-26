"""Tests for FINORA SaaS pricing (customer_fee), peak tracking, platform tenants fee column, and consultant handover (reassign)."""
import os
import time
import requests
import pytest

def _load_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
_load_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PW = "Finora2026!"


def _login(email, pw=PW):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def ryu():
    return _login("ryuichi.kurozaki@gmail.com")


@pytest.fixture(scope="module")
def cons():
    return _login("consultant@finora.co.jp")


# ---------- Pricing / subscription ----------
class TestSubscriptionPricing:
    def test_pro_pricing_shape(self, ryu):
        r = ryu.get(f"{BASE}/api/subscription", timeout=20)
        assert r.status_code == 200
        d = r.json()
        p = d["pricing"]
        for k in ("month", "current_customers", "peak_customers", "base_fee", "per_customer_fee", "months", "amount"):
            assert k in p, f"missing key {k}"
        assert p["base_fee"] == 5000
        assert p["per_customer_fee"] == 500
        assert p["months"] == 1
        assert d["plan"]["code"] == "PRO"
        # amount = (base + per*peak)*months
        assert p["amount"] == (p["base_fee"] + p["per_customer_fee"] * p["peak_customers"]) * p["months"]

    def test_consultant_cannot_read_subscription(self, cons):
        r = cons.get(f"{BASE}/api/subscription", timeout=20)
        # /subscription requires admin_only
        assert r.status_code == 403


# ---------- Peak logic ----------
class TestPeakLogic:
    def test_create_client_bumps_peak_delete_keeps_peak(self, ryu):
        # capture starting state
        r0 = ryu.get(f"{BASE}/api/subscription").json()["pricing"]
        base_peak = r0["peak_customers"]
        base_cur = r0["current_customers"]
        # Create a client
        payload = {"client_type": "individual", "name": f"TEST_peak_{int(time.time())}", "status": "active"}
        cr = ryu.post(f"{BASE}/api/data/clients", json=payload)
        assert cr.status_code in (200, 201), cr.text
        cid = cr.json()["id"]
        try:
            r1 = ryu.get(f"{BASE}/api/subscription").json()["pricing"]
            assert r1["current_customers"] == base_cur + 1
            assert r1["peak_customers"] >= max(base_peak, base_cur + 1)
            expected_peak = r1["peak_customers"]
            assert r1["amount"] == (5000 + 500 * expected_peak)
        finally:
            dr = ryu.delete(f"{BASE}/api/data/clients/{cid}")
            assert dr.status_code in (200, 204)
        # After delete: current drops, peak stays
        r2 = ryu.get(f"{BASE}/api/subscription").json()["pricing"]
        assert r2["current_customers"] == base_cur
        assert r2["peak_customers"] == expected_peak
        assert r2["amount"] == (5000 + 500 * expected_peak)


# ---------- Platform ----------
class TestPlatform:
    def test_platform_tenants_has_fee_and_peak(self, ryu):
        r = ryu.get(f"{BASE}/api/platform/tenants", timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 1
        for row in rows:
            assert "amount" in row
            assert "peak_customers" in row
            assert "customers" in row

    def test_platform_plans_has_base_per(self, ryu):
        r = ryu.get(f"{BASE}/api/platform/plans")
        assert r.status_code == 200
        plans = {p["code"]: p for p in r.json()}
        assert plans["PRO"]["base_fee"] == 5000
        assert plans["PRO"]["per_customer_fee"] == 500
        assert plans["TRIAL"].get("base_fee") in (0, None)

    def test_platform_admin_still_scoped_to_own_clients(self, ryu):
        """ryuichi (platform_admin, tenant owner, NOT is_consultant) sees all clients within own tenant only."""
        r = ryu.get(f"{BASE}/api/data/clients")
        assert r.status_code == 200
        clients = r.json()
        # find ryuichi tenant id
        me = ryu.get(f"{BASE}/api/auth/me").json()
        tid = me["tenant_id"]
        for c in clients:
            # server strips _id via clean; tenant_id should be present
            assert c.get("tenant_id") == tid


# ---------- TRIAL signup pricing = 0 ----------
class TestTrialSignup:
    @pytest.fixture(scope="class")
    def trial(self):
        email = f"TEST_trial_{int(time.time())}@example.test"
        payload = {"name": "Trial User", "company_name": "Trial Co", "email": email, "password": "Password123!", "plan_code": "TRIAL"}
        r = requests.post(f"{BASE}/api/public/signup", json=payload, timeout=30)
        if r.status_code == 429:
            pytest.skip("signup rate limited")
        assert r.status_code == 200, r.text
        s = _login(email, "Password123!")
        return s, email

    def test_trial_subscription_amount_zero(self, trial):
        s, _ = trial
        p = s.get(f"{BASE}/api/subscription").json()["pricing"]
        assert p["amount"] == 0
        assert p["base_fee"] == 0
        assert p["per_customer_fee"] == 0

    def test_trial_checkout_subscription_409(self, trial):
        s, _ = trial
        r = s.post(f"{BASE}/api/stripe/checkout/subscription", json={"origin_url": "https://example.test"})
        assert r.status_code == 409

    def test_trial_is_consultant_admin_cannot_reassign_others(self, trial, ryu):
        """A brand new signup admin (is_consultant=True) cannot reassign from another user id."""
        s, _ = trial
        # ryuichi's id as bogus from_id
        rid = ryu.get(f"{BASE}/api/auth/me").json()["id"]
        me = s.get(f"{BASE}/api/auth/me").json()
        r = s.post(f"{BASE}/api/clients/reassign", json={"from_id": rid, "to_id": me["id"], "client_ids": []})
        assert r.status_code == 403


# ---------- Handover ----------
class TestHandover:
    def test_same_from_to_returns_422(self, ryu):
        me = ryu.get(f"{BASE}/api/auth/me").json()
        r = ryu.post(f"{BASE}/api/clients/reassign", json={"from_id": me["id"], "to_id": me["id"], "client_ids": []})
        assert r.status_code == 422

    def test_reassign_and_restore(self, ryu, cons):
        # find one client owned by consultant@finora.co.jp
        cme = cons.get(f"{BASE}/api/auth/me").json()
        rme = ryu.get(f"{BASE}/api/auth/me").json()
        cons_clients = cons.get(f"{BASE}/api/data/clients").json()
        assert cons_clients, "consultant should have clients"
        target = cons_clients[0]
        cid = target["id"]
        # Move consultant -> ryuichi
        mv = ryu.post(f"{BASE}/api/clients/reassign", json={"from_id": cme["id"], "to_id": rme["id"], "client_ids": [cid]})
        assert mv.status_code == 200, mv.text
        assert mv.json()["moved"] == 1
        # Consultant no longer sees it
        after = cons.get(f"{BASE}/api/data/clients").json()
        assert cid not in [c["id"] for c in after]
        # Move back
        back = ryu.post(f"{BASE}/api/clients/reassign", json={"from_id": rme["id"], "to_id": cme["id"], "client_ids": [cid]})
        assert back.status_code == 200
        # Consultant sees it again
        restored = cons.get(f"{BASE}/api/data/clients").json()
        assert cid in [c["id"] for c in restored]
