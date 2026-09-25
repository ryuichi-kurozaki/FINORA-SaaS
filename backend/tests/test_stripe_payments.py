"""Backend tests for Stripe card payments (invoice + SaaS fee)."""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://investment-hub-309.preview.emergentagent.com").rstrip("/")
PW = "Finora2026!"


def login(email):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def owner():
    return login("ryuichi.kurozaki@gmail.com")


@pytest.fixture(scope="module")
def consultant():
    return login("consultant@finora.co.jp")


@pytest.fixture(scope="module")
def client1():
    return login("client@finora.co.jp")  # 佐藤 健一


@pytest.fixture(scope="module")
def client2():
    return login("client2@finora.co.jp")  # Ana Paula Ferreira


@pytest.fixture(scope="module")
def owner_b():
    return login("consultantb@finora.co.jp")


def _payable_invoice_id(headers, client_email_hint=None):
    r = requests.get(f"{BASE}/api/invoices", headers=headers)
    assert r.status_code == 200, r.text
    for inv in r.json():
        if inv["status"] in ("ISSUED", "PARTIALLY_PAID", "OVERDUE") and inv["balance"] > 0:
            return inv
    return None


# ---------- invoice checkout ----------

class TestInvoiceCheckout:
    def test_client_can_create_invoice_checkout(self, client1):
        inv = _payable_invoice_id(client1)
        if not inv:
            pytest.skip("no payable invoice for client1")
        r = requests.post(f"{BASE}/api/stripe/checkout/invoice",
                          json={"invoice_id": inv["id"], "origin_url": "https://example.com"},
                          headers=client1)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "checkout_url" in data and data["checkout_url"].startswith("https://")
        assert "session_id" in data and data["session_id"].startswith("cs_")

    def test_consultant_cannot_checkout(self, consultant):
        r = requests.get(f"{BASE}/api/invoices", headers=consultant)
        payable = [i for i in r.json() if i["status"] in ("ISSUED", "PARTIALLY_PAID", "OVERDUE") and i["balance"] > 0]
        if not payable:
            pytest.skip("no payable invoice visible to consultant")
        r = requests.post(f"{BASE}/api/stripe/checkout/invoice",
                          json={"invoice_id": payable[0]["id"], "origin_url": "https://example.com"},
                          headers=consultant)
        assert r.status_code == 403, r.text

    def test_owner_cannot_checkout(self, owner):
        inv = _payable_invoice_id(owner)
        if not inv:
            pytest.skip("no payable invoice")
        r = requests.post(f"{BASE}/api/stripe/checkout/invoice",
                          json={"invoice_id": inv["id"], "origin_url": "https://example.com"},
                          headers=owner)
        assert r.status_code == 403

    def test_client_cannot_pay_others_invoice(self, client1, client2):
        # find a payable invoice belonging to client1 (佐藤), then attempt as client2
        inv = _payable_invoice_id(client1)
        if not inv:
            pytest.skip("no payable invoice for client1")
        r = requests.post(f"{BASE}/api/stripe/checkout/invoice",
                          json={"invoice_id": inv["id"], "origin_url": "https://example.com"},
                          headers=client2)
        assert r.status_code in (403, 404), r.text

    def test_bad_invoice_id(self, client1):
        r = requests.post(f"{BASE}/api/stripe/checkout/invoice",
                          json={"invoice_id": "nonexistent", "origin_url": "https://example.com"},
                          headers=client1)
        assert r.status_code in (403, 404)


# ---------- payments status ----------

class TestPaymentStatus:
    def test_unknown_session(self):
        r = requests.get(f"{BASE}/api/payments/status/cs_test_unknown_xyz")
        assert r.status_code == 404

    def test_status_shape_no_auth_needed(self, client1):
        inv = _payable_invoice_id(client1)
        if not inv:
            pytest.skip("no payable invoice")
        r = requests.post(f"{BASE}/api/stripe/checkout/invoice",
                          json={"invoice_id": inv["id"], "origin_url": "https://example.com"},
                          headers=client1)
        sid = r.json()["session_id"]
        # unauthenticated status call
        r2 = requests.get(f"{BASE}/api/payments/status/{sid}")
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert set(d.keys()) == {"session_id", "status", "payment_status"}
        assert d["session_id"] == sid


# ---------- saas subscription ----------

class TestSaaSCheckout:
    def test_consultant_cannot_pay_saas(self, consultant):
        r = requests.post(f"{BASE}/api/stripe/checkout/subscription",
                          json={"origin_url": "https://example.com"}, headers=consultant)
        assert r.status_code == 403

    def test_tenant_b_amount_and_checkout(self, owner_b):
        # first, ensure amount not set → 409 (only if amount unset). We check current state.
        sub = requests.get(f"{BASE}/api/subscription", headers=owner_b).json()
        if not sub.get("subscription", {}).get("amount"):
            r = requests.post(f"{BASE}/api/stripe/checkout/subscription",
                              json={"origin_url": "https://example.com"}, headers=owner_b)
            assert r.status_code == 409, r.text

        # Ask platform admin to set amount
        platform = login("ryuichi.kurozaki@gmail.com")
        tenants = requests.get(f"{BASE}/api/platform/tenants", headers=platform).json()
        tb = next((t for t in tenants if "Bコンサルティング" in t.get("name", "") or "Bコンサル" in t.get("name", "")), None)
        assert tb, f"tenant B not found: {[t.get('name') for t in tenants]}"
        r = requests.put(f"{BASE}/api/platform/tenants/{tb['id']}", json={"amount": 9800}, headers=platform)
        assert r.status_code == 200, r.text

        # now checkout should work
        r = requests.post(f"{BASE}/api/stripe/checkout/subscription",
                          json={"origin_url": "https://example.com"}, headers=owner_b)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["checkout_url"].startswith("https://")
        assert data["session_id"].startswith("cs_")

        # status endpoint on the sub session
        rs = requests.get(f"{BASE}/api/payments/status/{data['session_id']}")
        assert rs.status_code == 200
        assert rs.json()["payment_status"] in ("pending", "unpaid")
