"""FINORA backend regression tests.

Covers auth (login, lockout, refresh, me), RBAC (admin/consultant/client),
CRUD via /api/data/{entity}, dashboard/simulation/ai/tasks/settings,
CSV/Excel I/O, documents (GridFS), field encryption at rest, audit logs.
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://investment-hub-309.preview.emergentagent.com"

ADMIN = ("ryuichi.kurozaki@gmail.com", "Finora2026!")
CONSULTANT = ("consultant@finora.co.jp", "Finora2026!")
CLIENT = ("client@finora.co.jp", "Finora2026!")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    return r


def _session(email, password):
    r = _login(email, password)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    tok = r.json()["access_token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s, r.json()["user"]


# -------- fixtures --------
@pytest.fixture(scope="session")
def admin_session():
    return _session(*ADMIN)


@pytest.fixture(scope="session")
def consultant_session():
    return _session(*CONSULTANT)


@pytest.fixture(scope="session")
def client_session():
    return _session(*CLIENT)


# -------- Auth --------
class TestAuth:
    def test_root(self):
        r = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_login_admin(self):
        r = _login(*ADMIN)
        assert r.status_code == 200
        j = r.json()
        assert j["user"]["role"] == "admin"
        assert j["user"]["email"] == ADMIN[0]
        assert isinstance(j["access_token"], str) and len(j["access_token"]) > 20
        # cookies set
        assert "access_token" in r.cookies or any(c.name == "access_token" for c in r.cookies)

    def test_login_bad_password(self):
        r = _login(ADMIN[0], "wrong-pw-xxx")
        assert r.status_code == 401

    def test_me(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
        assert "tenant" in r.json()

    def test_lockout_with_throwaway_email(self):
        # Use a random email so we don't lock the real admin.
        email = f"lockout_{uuid.uuid4().hex[:8]}@example.com"
        last = None
        for _ in range(5):
            last = _login(email, "bad")
            assert last.status_code == 401
        # 6th attempt should be 429
        r = _login(email, "bad")
        assert r.status_code == 429, f"expected 429 lockout, got {r.status_code} body={r.text}"


# -------- RBAC --------
class TestRBAC:
    def test_admin_sees_all_clients(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{BASE_URL}/api/data/clients", timeout=10)
        assert r.status_code == 200
        names = [c.get("corporate_name") or c.get("name") for c in r.json()]
        assert any("サクラ不動産" in (n or "") for n in names), f"admin should see サクラ不動産; got {names}"
        assert len(r.json()) >= 4

    def test_consultant_sees_only_assigned(self, consultant_session):
        s, _ = consultant_session
        r = s.get(f"{BASE_URL}/api/data/clients", timeout=10)
        assert r.status_code == 200
        names = [c.get("corporate_name") or c.get("name") for c in r.json()]
        assert not any("サクラ不動産" in (n or "") for n in names), f"consultant must NOT see サクラ不動産; got {names}"
        assert len(r.json()) == 3

    def test_client_sees_only_own(self, client_session):
        s, user = client_session
        r = s.get(f"{BASE_URL}/api/data/clients", timeout=10)
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["id"] == user.get("client_id")

    def test_client_no_nav_to_clients_create(self, client_session):
        s, _ = client_session
        r = s.post(f"{BASE_URL}/api/data/clients", json={"name": "hack"}, timeout=10)
        assert r.status_code == 403

    def test_client_cannot_access_other_client_data(self, client_session, admin_session):
        s_client, cuser = client_session
        s_admin, _ = admin_session
        all_clients = s_admin.get(f"{BASE_URL}/api/data/clients").json()
        other = [c for c in all_clients if c["id"] != cuser["client_id"]][0]
        # try to fetch assets scoped to another client
        r = s_client.get(f"{BASE_URL}/api/data/assets", params={"client_id": other["id"]}, timeout=10)
        assert r.status_code == 403


# -------- CRUD --------
class TestCRUD:
    def test_create_read_update_delete_asset(self, admin_session):
        s, _ = admin_session
        clients = s.get(f"{BASE_URL}/api/data/clients").json()
        cid = clients[0]["id"]
        payload = {
            "client_id": cid, "asset_class": "jp_stock", "name": "TEST_STOCK", "ticker": "9999",
            "owner_type": "individual", "country": "JP", "sector": "test", "currency": "JPY",
            "acquired_date": "2024-01-01", "acquisition_price": 100, "quantity": 10, "current_price": 150,
            "realized_pl": 0, "dividend_annual": 0, "interest_annual": 0,
        }
        r = s.post(f"{BASE_URL}/api/data/assets", json=payload, timeout=10)
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        # value_jpy/pl computed on list
        lst = s.get(f"{BASE_URL}/api/data/assets", params={"client_id": cid}).json()
        got = [a for a in lst if a["id"] == aid][0]
        assert got.get("value_jpy") is not None
        assert got.get("name") == "TEST_STOCK"
        # update
        r = s.put(f"{BASE_URL}/api/data/assets/{aid}", json={**payload, "name": "TEST_STOCK_UPD"})
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_STOCK_UPD"
        # delete
        r = s.delete(f"{BASE_URL}/api/data/assets/{aid}")
        assert r.status_code == 200
        r = s.get(f"{BASE_URL}/api/data/assets/{aid}")
        assert r.status_code == 404

    def test_client_readonly_post_forbidden(self, client_session):
        s, _ = client_session
        r = s.post(f"{BASE_URL}/api/data/assets", json={"client_id": "x", "asset_class": "cash", "name": "X"})
        assert r.status_code == 403


# -------- Dashboard / analytics / AI --------
class TestAnalyticsAI:
    def test_dashboard(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{BASE_URL}/api/analytics/dashboard?lang=ja", timeout=20)
        assert r.status_code == 200
        j = r.json()
        for k in ("summary", "cashflow", "trend", "metrics", "risk", "breakdowns", "projection", "insights", "counts"):
            assert k in j, f"missing key {k}"
        assert j["engine"] == "finora-rule-engine-v1"
        for g in ("changes", "risks", "checks", "since_last", "missing", "summary"):
            assert g in j["insights"], f"insight group {g} missing"

    def test_dashboard_langs(self, admin_session):
        s, _ = admin_session
        for lang in ("ja", "en", "pt"):
            r = s.get(f"{BASE_URL}/api/analytics/dashboard?lang={lang}", timeout=20)
            assert r.status_code == 200

    def test_simulation(self, admin_session):
        s, _ = admin_session
        r = s.post(f"{BASE_URL}/api/simulation", json={"params": {"years": 10}}, timeout=15)
        assert r.status_code == 200
        assert "rows" in r.json() and len(r.json()["rows"]) > 0

    def test_ai_ask(self, admin_session):
        s, _ = admin_session
        r = s.post(f"{BASE_URL}/api/ai/ask", json={"question": "リスクは？", "lang": "ja"}, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j["engine"] == "finora-rule-engine-v1"
        assert j["intent"] == "risk"
        assert isinstance(j["sections"], list) and len(j["sections"]) > 0

    def test_ai_report(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{BASE_URL}/api/ai/report?lang=en", timeout=20)
        assert r.status_code == 200
        assert len(r.json()["sections"]) > 0

    def test_task_alerts(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{BASE_URL}/api/tasks/alerts", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_settings_get(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{BASE_URL}/api/settings", timeout=10)
        assert r.status_code == 200
        assert "fx" in r.json()
        assert r.json()["base_currency"] == "JPY"


# -------- I/O --------
class TestIO:
    def test_export_csv(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{BASE_URL}/api/io/export/assets?fmt=csv", timeout=20)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert len(r.content) > 0

    def test_export_xlsx(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{BASE_URL}/api/io/export/assets?fmt=xlsx", timeout=30)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "")

    def test_import_csv(self, admin_session):
        s, _ = admin_session
        clients = s.get(f"{BASE_URL}/api/data/clients").json()
        cid = clients[0]["id"]
        csv = "direction,category,name,amount,frequency\nincome,other,TEST_CF_IMPORT,1000,monthly\n"
        files = {"file": ("cf.csv", csv, "text/csv")}
        # requests without JSON content-type
        r = requests.post(f"{BASE_URL}/api/io/import/cashflows",
                          headers={"Authorization": s.headers["Authorization"]},
                          files=files, data={"client_id": cid}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 1


# -------- Documents --------
class TestDocuments:
    def test_upload_list_download_delete(self, admin_session):
        s, _ = admin_session
        clients = s.get(f"{BASE_URL}/api/data/clients").json()
        cid = clients[0]["id"]
        files = {"file": ("test.txt", b"hello finora", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/documents",
                          headers={"Authorization": s.headers["Authorization"]},
                          files=files, data={"client_id": cid, "category": "other", "notes": "TEST"}, timeout=20)
        assert r.status_code == 200, r.text
        did = r.json()["id"]
        # list
        lst = s.get(f"{BASE_URL}/api/documents", params={"client_id": cid}).json()
        assert any(d["id"] == did for d in lst)
        # download
        r = s.get(f"{BASE_URL}/api/documents/{did}/download", timeout=15)
        assert r.status_code == 200
        assert r.content == b"hello finora"
        # delete
        r = s.delete(f"{BASE_URL}/api/documents/{did}")
        assert r.status_code == 200


# -------- Field encryption + audit before/after --------
class TestEncryptionAndAudit:
    def test_encryption_at_rest_and_decrypted_via_api(self, admin_session):
        """Create a client (with encrypted fields), check DB stores 'enc:' but API returns plaintext.
        Uses admin session; verifies via audit_logs.after which should have the encrypted phone."""
        s, _ = admin_session
        payload = {"client_type": "individual", "name": "TEST_ENC_CLIENT",
                   "phone": "090-0000-0000", "address": "TEST_ADDRESS_ENC", "notes": "TEST_NOTES_ENC",
                   "email": "test_enc@example.com"}
        r = s.post(f"{BASE_URL}/api/data/clients", json=payload, timeout=10)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        try:
            # API returns decrypted
            got = s.get(f"{BASE_URL}/api/data/clients/{cid}").json()
            assert got["phone"] == "090-0000-0000"
            assert got["address"] == "TEST_ADDRESS_ENC"
            assert got["notes"] == "TEST_NOTES_ENC"
            # Audit logs should have the create with 'after' payload (stored form)
            logs = s.get(f"{BASE_URL}/api/security/audit-logs?entity=clients", timeout=15).json()
            found = [l for l in logs if l.get("entity_id") == cid and l["action"] == "create"]
            assert found, "audit create log not found"
            after = found[0]["after"]
            # Stored form is encrypted (enc: prefix)
            assert isinstance(after.get("phone"), str) and after["phone"].startswith("enc:"), \
                f"phone should be encrypted in audit.after; got {after.get('phone')!r}"
            # Now update and confirm before/after present
            r = s.put(f"{BASE_URL}/api/data/clients/{cid}", json={**payload, "notes": "TEST_NOTES_UPDATED"})
            assert r.status_code == 200
            logs = s.get(f"{BASE_URL}/api/security/audit-logs?entity=clients").json()
            upd = [l for l in logs if l.get("entity_id") == cid and l["action"] == "update"]
            assert upd, "audit update log missing"
            assert upd[0]["before"] is not None and upd[0]["after"] is not None
        finally:
            s.delete(f"{BASE_URL}/api/data/clients/{cid}")


# -------- Change password (revert) --------
class TestChangePassword:
    def test_change_password_and_revert(self):
        # login as admin, change to temp, revert
        s, _ = _session(*ADMIN)
        temp = "TempPass_2026!"
        r = s.post(f"{BASE_URL}/api/auth/change-password",
                   json={"current_password": ADMIN[1], "new_password": temp}, timeout=15)
        assert r.status_code == 200
        # login with temp works
        r = _login(ADMIN[0], temp)
        assert r.status_code == 200
        # revert
        tok = r.json()["access_token"]
        r = requests.post(f"{BASE_URL}/api/auth/change-password",
                          headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                          json={"current_password": temp, "new_password": ADMIN[1]}, timeout=15)
        assert r.status_code == 200
        # Final check
        r = _login(*ADMIN)
        assert r.status_code == 200
