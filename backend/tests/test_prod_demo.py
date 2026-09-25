"""
Production demo tenant tests (PRODUCTION https://www.finora.co.jp).
Covers: demo user login, data isolation, platform-admin denial, forbid_demo restrictions,
read-endpoint access for all roles. One (and only one) login attempt for real admin.
Preview regression: demo login on preview host.
"""
import os
import pytest
import requests

PROD = "https://www.finora.co.jp"
PREVIEW = os.environ.get("REACT_APP_BACKEND_URL", "https://investment-hub-309.preview.emergentagent.com").rstrip("/")

DEMO_PW = "FinoraDemo2026!"
PREVIEW_PW = "Finora2026!"

DEMO_USERS = {
    "admin":      "demo-admin@finora.co.jp",
    "consultant": "demo-consultant@finora.co.jp",
    "client":     "demo-client@finora.co.jp",
}

PREVIEW_DEMO_USERS = {
    "admin":      "ryuichi.kurozaki@gmail.com",
    "consultant": "consultant@finora.co.jp",
    "client":     "client@finora.co.jp",
}


def _login(base, email, pw):
    r = requests.post(f"{base}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    return r


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def prod_tokens():
    toks = {}
    for role, email in DEMO_USERS.items():
        r = _login(PROD, email, DEMO_PW)
        assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
        j = r.json()
        assert "access_token" in j, f"no token in {j}"
        toks[role] = j["access_token"]
    return toks


# ---------- LOGIN ----------
def test_prod_demo_logins_all_roles(prod_tokens):
    assert set(prod_tokens.keys()) == {"admin", "consultant", "client"}


# ---------- DATA ISOLATION ----------
def test_prod_demo_admin_sees_only_demo_clients(prod_tokens):
    r = requests.get(f"{PROD}/api/data/clients", headers=_hdr(prod_tokens["admin"]), timeout=20)
    assert r.status_code == 200, r.text[:200]
    clients = r.json()
    assert isinstance(clients, list)
    names = [c.get("name", "") for c in clients]
    # must not include real tenant client
    assert not any("決済テスト" in n for n in names), f"leaked real client: {names}"
    # must include at least one demo client (seed had 佐藤 健一 among 4)
    assert len(clients) >= 1, "no demo clients returned"


def test_prod_demo_admin_invoices_no_real_data(prod_tokens):
    # Invoice numbers restart per tenant (INV-YYYYMM-####), so verify by client_id set
    r_c = requests.get(f"{PROD}/api/data/clients", headers=_hdr(prod_tokens["admin"]), timeout=20)
    assert r_c.status_code == 200
    demo_client_ids = {c["id"] for c in r_c.json()}
    r = requests.get(f"{PROD}/api/invoices", headers=_hdr(prod_tokens["admin"]), timeout=20)
    assert r.status_code == 200, r.text[:200]
    inv = r.json()
    for i in inv if isinstance(inv, list) else []:
        assert i.get("client_id") in demo_client_ids, f"invoice for non-demo client leaked: {i}"


def test_prod_demo_admin_no_platform_access(prod_tokens):
    r = requests.get(f"{PROD}/api/platform/tenants", headers=_hdr(prod_tokens["admin"]), timeout=20)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"


# ---------- READ ENDPOINTS WORK FOR ALL 3 ROLES ----------
@pytest.mark.parametrize("role", ["admin", "consultant", "client"])
def test_prod_demo_read_endpoints(prod_tokens, role):
    tok = prod_tokens[role]
    # analytics dashboard
    r = requests.get(f"{PROD}/api/analytics/dashboard", headers=_hdr(tok), timeout=20)
    assert r.status_code == 200, f"[{role}] analytics/dashboard {r.status_code} {r.text[:200]}"
    # invoices list
    r2 = requests.get(f"{PROD}/api/invoices", headers=_hdr(tok), timeout=20)
    assert r2.status_code == 200, f"[{role}] invoices {r2.status_code} {r2.text[:200]}"


# ---------- FORBID_DEMO RESTRICTIONS ----------
def test_prod_demo_change_password_forbidden(prod_tokens):
    r = requests.post(f"{PROD}/api/auth/change-password",
                      headers=_hdr(prod_tokens["admin"]),
                      json={"current_password": DEMO_PW, "new_password": "Whatever123!"}, timeout=20)
    assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"
    # password must remain unchanged - verify by re-login
    r2 = _login(PROD, DEMO_USERS["admin"], DEMO_PW)
    assert r2.status_code == 200, f"demo admin password changed! login now returns {r2.status_code}"


def test_prod_demo_2fa_setup_forbidden(prod_tokens):
    r = requests.post(f"{PROD}/api/auth/2fa/setup", headers=_hdr(prod_tokens["admin"]), timeout=20)
    assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"


def test_prod_demo_create_user_forbidden(prod_tokens):
    r = requests.post(f"{PROD}/api/users",
                      headers=_hdr(prod_tokens["admin"]),
                      json={"email": "TEST_demo_denied@example.com", "name": "x", "role": "client"}, timeout=20)
    assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"


def test_prod_demo_billing_profile_put_forbidden(prod_tokens):
    r = requests.put(f"{PROD}/api/billing/profile",
                     headers=_hdr(prod_tokens["admin"]),
                     json={"company_name": "TEST DEMO"}, timeout=20)
    assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"


def test_prod_demo_stripe_checkout_invoice_forbidden(prod_tokens):
    # client role — need an invoice id from demo tenant
    inv = requests.get(f"{PROD}/api/invoices", headers=_hdr(prod_tokens["client"]), timeout=20).json()
    if not isinstance(inv, list) or not inv:
        pytest.skip("no demo invoices visible to demo client")
    iid = inv[0].get("id")
    r = requests.post(f"{PROD}/api/stripe/checkout/invoice",
                      headers=_hdr(prod_tokens["client"]),
                      json={"invoice_id": iid, "origin_url": "https://www.finora.co.jp"}, timeout=20)
    assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"


def test_prod_demo_stripe_refund_forbidden(prod_tokens):
    inv = requests.get(f"{PROD}/api/invoices", headers=_hdr(prod_tokens["admin"]), timeout=20).json()
    iid = (inv[0].get("id") if isinstance(inv, list) and inv else "nonexistent")
    r = requests.post(f"{PROD}/api/stripe/refund/invoice/{iid}",
                      headers=_hdr(prod_tokens["admin"]),
                      json={}, timeout=20)
    assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"


# ---------- PROD REAL ADMIN (single attempt) ----------
def test_prod_real_admin_login_once():
    r = _login(PROD, "ryuichi.kurozaki@gmail.com", "FntOjOWUB0UOcvu8#7")
    assert r.status_code == 200, f"real admin login broken: {r.status_code} {r.text[:200]}"
    j = r.json()
    assert "access_token" in j or j.get("requires_2fa")


# ---------- PREVIEW REGRESSION ----------
@pytest.mark.parametrize("role,email", list(PREVIEW_DEMO_USERS.items()))
def test_preview_demo_login(role, email):
    r = _login(PREVIEW, email, PREVIEW_PW)
    assert r.status_code == 200, f"[preview {role}] {r.status_code} {r.text[:200]}"
    j = r.json()
    assert "access_token" in j or j.get("requires_2fa"), f"no token: {j}"
