"""FINORA v2 spec tests: client-owned data, RBAC, corrections, requests, comments, notifications,
positions, data-health, goals, history/snapshots, tasks, consents, 2FA, admin backup, audit, export, timeline."""
import os
import io
import json
import time
import uuid
import pytest
import requests
import pyotp

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://investment-hub-309.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = ("ryuichi.kurozaki@gmail.com", "Finora2026!")
CONSULTANT = ("consultant@finora.co.jp", "Finora2026!")
CLIENT_A = ("client@finora.co.jp", "Finora2026!")   # 佐藤 健一
CLIENT_B = ("client2@finora.co.jp", "Finora2026!")  # Ana Paula Ferreira


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    # keep cookies for cookie-based endpoints
    for k, v in r.cookies.items():
        s.cookies.set(k, v)
    me = s.get(f"{API}/auth/me", timeout=10).json()
    s.user = me
    return s


@pytest.fixture(scope="session")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="session")
def consultant():
    return _login(*CONSULTANT)


@pytest.fixture(scope="session")
def client_a():
    return _login(*CLIENT_A)


@pytest.fixture(scope="session")
def client_b():
    return _login(*CLIENT_B)


@pytest.fixture(scope="session")
def client_ids(admin):
    """Return dict: name->client_id and role client_ids."""
    r = admin.get(f"{API}/data/clients", timeout=15)
    assert r.status_code == 200
    items = r.json()
    by_name = {i.get("name") or i.get("corporate_name"): i["id"] for i in items}
    # Consultant clients: 佐藤 健一, ノヴァテック(株), Ana Paula Ferreira
    # Admin-only client: 株式会社サクラ不動産
    return {"all": items, "by_name": by_name}


# ---------------- Cross-client isolation (Client A cannot access Client B) ----------------
class TestClientIsolation:
    def test_client_a_cannot_read_client_b_assets(self, client_a, client_b):
        b_cid = client_b.user["client_id"]
        r = client_a.get(f"{API}/data/assets?client_id={b_cid}")
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_client_a_cannot_read_client_b_positions(self, client_a, client_b):
        b_cid = client_b.user["client_id"]
        r = client_a.get(f"{API}/positions?client_id={b_cid}")
        assert r.status_code == 403

    def test_client_a_cannot_read_client_b_history(self, client_a, client_b):
        b_cid = client_b.user["client_id"]
        r = client_a.get(f"{API}/history?client_id={b_cid}")
        assert r.status_code == 403

    def test_client_a_cannot_read_client_b_timeline(self, client_a, client_b):
        b_cid = client_b.user["client_id"]
        r = client_a.get(f"{API}/timeline?client_id={b_cid}")
        assert r.status_code == 403

    def test_client_a_cannot_read_client_b_corrections(self, client_a, client_b):
        b_cid = client_b.user["client_id"]
        r = client_a.get(f"{API}/corrections?client_id={b_cid}")
        assert r.status_code == 403

    def test_client_a_ai_ask_other_client_id_forbidden(self, client_a, client_b):
        b_cid = client_b.user["client_id"]
        r = client_a.post(f"{API}/ai/ask", json={"client_id": b_cid, "question": "hi", "lang": "ja"})
        assert r.status_code == 403

    def test_client_export_forced_to_own(self, client_a, client_b):
        # export with other client_id -> should 403 (scope enforces access)
        b_cid = client_b.user["client_id"]
        r = client_a.get(f"{API}/io/export/assets?client_id={b_cid}")
        assert r.status_code == 403


# ---------------- Consultant read-only on client-owned entities ----------------
class TestConsultantReadOnly:
    OWNED = ["assets", "accounts", "liabilities", "cashflows", "transactions", "goals"]

    def test_consultant_forbidden_writes(self, consultant, client_a):
        cid = client_a.user["client_id"]
        for e in self.OWNED:
            payload = {"client_id": cid, "name": "TEST_x", "asset_class": "jp_stock",
                       "institution": "TEST", "liability_type": "other", "direction": "income",
                       "category": "salary", "amount": 1, "date": "2026-01-01", "tx_type": "buy",
                       "target_amount": 1, "target_date": "2027-01-01"}
            r = consultant.post(f"{API}/data/{e}", json=payload)
            assert r.status_code == 403, f"consultant POST /data/{e} expected 403, got {r.status_code}: {r.text[:200]}"

    def test_consultant_cannot_upload_document(self, consultant, client_a):
        cid = client_a.user["client_id"]
        files = {"file": ("t.pdf", b"%PDF-1.4 test", "application/pdf")}
        r = consultant.post(f"{API}/documents", data={"client_id": cid, "category": "other"}, files=files)
        assert r.status_code == 403

    def test_consultant_no_access_to_admin_only_client(self, consultant, client_ids):
        # 株式会社サクラ不動産 is admin-owned
        sakura = client_ids["by_name"].get("株式会社サクラ不動産")
        if not sakura:
            pytest.skip("Sakura client not seeded")
        r = consultant.get(f"{API}/data/assets?client_id={sakura}")
        assert r.status_code == 403


# ---------------- Client CRUD own data ----------------
class TestClientCRUD:
    def test_client_can_create_update_delete_asset(self, client_a):
        cid = client_a.user["client_id"]
        payload = {"client_id": cid, "asset_class": "jp_stock", "name": "TEST_ASSET_" + uuid.uuid4().hex[:6],
                   "currency": "JPY", "quantity": 100, "acquisition_price": 1000, "current_price": 1100}
        r = client_a.post(f"{API}/data/assets", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["source"] == "MANUAL"
        assert d["updated_by_role"] == "client"
        aid = d["id"]
        # update
        r2 = client_a.put(f"{API}/data/assets/{aid}", json={**payload, "current_price": 1200})
        assert r2.status_code == 200
        assert r2.json()["current_price"] == 1200
        # delete
        r3 = client_a.delete(f"{API}/data/assets/{aid}")
        assert r3.status_code == 200

    def test_client_notifies_consultant_on_update(self, client_a, consultant):
        cid = client_a.user["client_id"]
        # mark all read then create -> consultant should have new unread
        consultant.post(f"{API}/notifications/read-all")
        before = consultant.get(f"{API}/notifications").json()["unread"]
        payload = {"client_id": cid, "name": "TEST_G_" + uuid.uuid4().hex[:6], "category": "net_worth",
                   "target_amount": 1000000, "target_date": "2030-12-31", "priority": "low"}
        r = client_a.post(f"{API}/data/goals", json=payload)
        assert r.status_code == 200
        gid = r.json()["id"]
        time.sleep(0.5)
        after = consultant.get(f"{API}/notifications").json()
        assert after["unread"] > before, f"expected new notification, before={before} after={after['unread']}"
        assert any(n.get("kind") == "client_data_updated" for n in after["items"])
        client_a.delete(f"{API}/data/goals/{gid}")


# ---------------- Audit logs ----------------
class TestAuditLogs:
    def test_admin_audit_logs_uppercase_and_fields(self, admin):
        r = admin.get(f"{API}/security/audit-logs")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) > 0
        expected_actions = {"CREATE", "UPDATE", "DELETE", "LOGIN"}
        actions = {l["action"] for l in logs}
        assert expected_actions & actions, f"missing core actions; got {actions}"
        # every log has user_role
        for l in logs[:20]:
            assert "user_role" in l
            assert l["action"] == l["action"].upper()

    def test_consultant_forbidden_audit_logs(self, consultant):
        r = consultant.get(f"{API}/security/audit-logs")
        assert r.status_code == 403

    def test_delete_before_snapshot_kept(self, client_a, admin):
        cid = client_a.user["client_id"]
        payload = {"client_id": cid, "asset_class": "jp_stock", "name": "TEST_DEL_" + uuid.uuid4().hex[:6],
                   "currency": "JPY", "quantity": 1, "acquisition_price": 1, "current_price": 1}
        aid = client_a.post(f"{API}/data/assets", json=payload).json()["id"]
        client_a.delete(f"{API}/data/assets/{aid}")
        time.sleep(0.3)
        logs = admin.get(f"{API}/security/audit-logs?entity=assets").json()
        del_log = next((l for l in logs if l.get("entity_id") == aid and l["action"] == "DELETE"), None)
        assert del_log is not None, "DELETE audit log not found"
        assert del_log.get("before") is not None, "before snapshot not kept on DELETE"
        assert del_log["before"].get("name", "").startswith("TEST_DEL_")


# ---------------- Correction flow ----------------
class TestCorrectionFlow:
    def test_full_flow(self, consultant, client_a):
        cid = client_a.user["client_id"]
        # Consultant creates
        r = consultant.post(f"{API}/corrections", json={"client_id": cid, "target_entity": "assets",
                                                        "target_label": "TEST correction", "reason": "TEST_r",
                                                        "requested_change": "TEST_c"})
        assert r.status_code == 200, r.text
        corr = r.json()
        cid_corr = corr["id"]
        # Client sees notification
        time.sleep(0.3)
        n = client_a.get(f"{API}/notifications").json()
        assert any(x.get("kind") == "correction_requested" for x in n["items"])
        # Consultant cannot resolve
        rr = consultant.put(f"{API}/corrections/{cid_corr}/resolve", json={"note": "no"})
        assert rr.status_code == 403
        # Client resolves
        rr2 = client_a.put(f"{API}/corrections/{cid_corr}/resolve", json={"note": "done"})
        assert rr2.status_code == 200
        # Consultant close
        rr3 = consultant.put(f"{API}/corrections/{cid_corr}/close")
        assert rr3.status_code == 200

    def test_client_cannot_create_correction(self, client_a):
        cid = client_a.user["client_id"]
        r = client_a.post(f"{API}/corrections", json={"client_id": cid, "target_entity": "assets",
                                                     "reason": "x", "requested_change": "y"})
        assert r.status_code == 403


# ---------------- Consulting requests ----------------
class TestConsultingRequests:
    def test_flow(self, client_a, consultant):
        r = client_a.post(f"{API}/requests", json={"category": "portfolio", "title": "TEST_REQ",
                                                    "content": "test content"})
        assert r.status_code == 200
        rid = r.json()["id"]
        # Client cannot manage
        r2 = client_a.put(f"{API}/requests/{rid}/manage", json={"status": "accepted"})
        assert r2.status_code == 403
        # Consultant manages
        r3 = consultant.put(f"{API}/requests/{rid}/manage", json={"status": "accepted", "answer": "TEST_ans",
                                                                   "meeting_at": "2026-06-01T10:00:00"})
        assert r3.status_code == 200

    def test_consultant_cannot_create_request(self, consultant):
        r = consultant.post(f"{API}/requests", json={"category": "portfolio", "title": "x", "content": "y"})
        assert r.status_code == 403


# ---------------- Comments & Notifications ----------------
class TestCommentsNotifications:
    def test_comments_and_read(self, client_a, consultant):
        cid = client_a.user["client_id"]
        r = client_a.post(f"{API}/comments", json={"client_id": cid, "target_type": "assets",
                                                    "target_label": "TEST_C", "body": "hello"})
        assert r.status_code == 200
        r2 = consultant.get(f"{API}/comments?client_id={cid}")
        assert r2.status_code == 200
        assert any(c.get("body") == "hello" for c in r2.json())
        # read all
        assert consultant.post(f"{API}/notifications/read-all").status_code == 200
        assert consultant.get(f"{API}/notifications").json()["unread"] == 0


# ---------------- Positions / Health / Goals ----------------
class TestDerived:
    def test_positions_for_client_a(self, consultant, client_a):
        cid = client_a.user["client_id"]
        r = consultant.get(f"{API}/positions?client_id={cid}")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        if rows:
            row = rows[0]
            for k in ("avg_cost", "realized", "qty", "qty_mismatch"):
                assert k in row

    def test_data_health(self, consultant, client_a):
        cid = client_a.user["client_id"]
        r = consultant.get(f"{API}/data-health?client_id={cid}")
        assert r.status_code == 200
        h = r.json()
        assert "score" in h and "status" in h and "checks" in h
        assert h["status"] in ("ok", "review", "attention")

    def test_goals_progress(self, consultant, client_a):
        cid = client_a.user["client_id"]
        r = consultant.get(f"{API}/goals/progress?client_id={cid}")
        assert r.status_code == 200
        goals = r.json()
        nw = [g for g in goals if g.get("category") == "net_worth"]
        if nw:
            g = nw[0]
            assert "progress_pct" in g
            assert "simulation" in g


# ---------------- History / Snapshots ----------------
class TestHistorySnapshots:
    def test_history_daily(self, consultant, client_a):
        cid = client_a.user["client_id"]
        r = consultant.get(f"{API}/history?client_id={cid}")
        assert r.status_code == 200
        series = r.json()
        assert isinstance(series, list)
        assert len(series) > 0

    def test_snapshot_save_and_list(self, consultant, client_a):
        cid = client_a.user["client_id"]
        r = consultant.post(f"{API}/snapshots", json={"client_id": cid, "label": "TEST_SNAP"})
        assert r.status_code == 200
        r2 = consultant.get(f"{API}/snapshots?client_id={cid}")
        assert r2.status_code == 200
        assert any(s.get("label") == "TEST_SNAP" for s in r2.json())


# ---------------- Tasks visibility ----------------
class TestTasks:
    def test_client_cannot_edit_consultant_task(self, consultant, client_a):
        cid = client_a.user["client_id"]
        # consultant creates internal task
        r = consultant.post(f"{API}/data/tasks", json={"client_id": cid, "kind": "note", "title": "TEST_TASK_INT",
                                                        "priority": "low", "status": "open", "visibility": "internal"})
        assert r.status_code == 200
        tid = r.json()["id"]
        # client cannot see (internal)
        listing = client_a.get(f"{API}/data/tasks").json()
        assert not any(t["id"] == tid for t in listing)
        # client cannot edit even if forced
        r2 = client_a.put(f"{API}/data/tasks/{tid}", json={"title": "hack"})
        assert r2.status_code in (403, 404)
        consultant.delete(f"{API}/data/tasks/{tid}")


# ---------------- Consents ----------------
class TestConsents:
    def test_consultant_no_required(self, consultant):
        r = consultant.get(f"{API}/consents/status")
        assert r.status_code == 200
        assert r.json()["required"] == []


# ---------------- 2FA ----------------
class TestTwoFA:
    def test_2fa_full_cycle(self, consultant):
        # setup
        r = consultant.post(f"{API}/auth/2fa/setup")
        assert r.status_code == 200
        secret = r.json()["secret"]
        code = pyotp.TOTP(secret).now()
        r2 = consultant.post(f"{API}/auth/2fa/enable", json={"code": code})
        assert r2.status_code == 200, r2.text
        # login now requires 2fa
        lr = requests.post(f"{API}/auth/login", json={"email": CONSULTANT[0], "password": CONSULTANT[1]})
        assert lr.status_code == 200
        body = lr.json()
        assert body.get("requires_2fa") is True
        challenge = body["challenge_token"]
        # wait for a new code window if same as prev
        time.sleep(1)
        code2 = pyotp.TOTP(secret).now()
        vr = requests.post(f"{API}/auth/2fa/verify", json={"challenge_token": challenge, "code": code2})
        assert vr.status_code == 200, vr.text
        # disable using SAME session (consultant) — need a fresh code
        time.sleep(1)
        code3 = pyotp.TOTP(secret).now()
        dr = consultant.post(f"{API}/auth/2fa/disable", json={"code": code3})
        assert dr.status_code == 200, dr.text


# ---------------- Admin backup ----------------
class TestBackup:
    def test_admin_backup(self, admin):
        r = admin.get(f"{API}/admin/backup")
        assert r.status_code == 200
        assert "application/json" in r.headers.get("content-type", "")
        data = json.loads(r.content)
        for k in ("clients", "assets", "consents"):
            assert k in data

    def test_consultant_forbidden_backup(self, consultant):
        r = consultant.get(f"{API}/admin/backup")
        assert r.status_code == 403


# ---------------- Reports log ----------------
class TestReports:
    def test_report_log(self, consultant, client_a):
        cid = client_a.user["client_id"]
        for rtype in ("rpt_goals", "rpt_data_health", "rpt_transactions"):
            r = consultant.post(f"{API}/reports/log", json={"client_id": cid, "report_type": rtype})
            assert r.status_code == 200


# ---------------- Export as client forced to own ----------------
class TestExport:
    def test_client_export_own_ok(self, client_a):
        r = client_a.get(f"{API}/io/export/assets")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
