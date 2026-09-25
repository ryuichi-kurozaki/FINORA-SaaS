"""Consultant (is_consultant admin) isolation tests.

Verifies: A signup consultant (role=admin, is_consultant=true) only sees their own
clients / assets / tasks, and cannot read/create/update/delete another consultant's
client in the same tenant.
Also regression-checks FINORA admin (no is_consultant), staff consultant, and client roles.
"""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://investment-hub-309.preview.emergentagent.com"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

mc = MongoClient(MONGO_URL)
db = mc[DB_NAME]


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return s


# ---------- Module-scoped signup fixture (rate-limited 5/IP/hour) ----------
@pytest.fixture(scope="module")
def consultant_a():
    suffix = uuid.uuid4().hex[:10]
    email = f"consultant_a_{suffix}@example.test"
    password = "TestPass2026!"
    body = {"name": "Consultant A", "company_name": "A LLC", "email": email,
            "password": password, "plan_code": "TRIAL"}
    r = requests.post(f"{BASE}/api/public/signup", json=body, timeout=30)
    if r.status_code == 429:
        pytest.skip("Signup rate limited (5/IP/hour). Try later.")
    assert r.status_code == 200, f"signup -> {r.status_code} {r.text}"
    tid = r.json()["tenant_id"]
    session = _login(email, password)
    me = session.get(f"{BASE}/api/auth/me", timeout=30).json()
    yield {"session": session, "email": email, "password": password, "tenant_id": tid,
           "user_id": me["id"], "role": me["role"], "is_consultant": me.get("is_consultant")}
    # Cleanup: delete everything in this tenant
    for coll in ("users", "clients", "assets", "tenants", "saas_subscriptions",
                 "settings", "sessions", "audit_logs", "invoices", "tasks"):
        try:
            db[coll].delete_many({"tenant_id": tid})
        except Exception:
            pass
    # cleanup users by created email (staff)
    db.users.delete_many({"email": {"$regex": f"^staff_{suffix}"}})


@pytest.fixture(scope="module")
def env(consultant_a):
    """Set up: 1 A-owned client, 1 staff consultant with 1 staff-owned client + 1 asset."""
    s = consultant_a["session"]
    tid = consultant_a["tenant_id"]
    a_uid = consultant_a["user_id"]

    # Verify signup made A an is_consultant admin
    assert consultant_a["role"] == "admin"
    assert consultant_a["is_consultant"] is True

    # Create A's own client via API
    r = s.post(f"{BASE}/api/data/clients",
               json={"client_type": "individual", "name": "A顧客"}, timeout=30)
    assert r.status_code == 200, f"create A client -> {r.status_code} {r.text}"
    a_client = r.json()
    assert a_client["consultant_id"] == a_uid, "A's client must be assigned to A"

    # Create staff consultant user via /api/users (A is admin)
    suffix = uuid.uuid4().hex[:8]
    staff_email = f"staff_{suffix}@example.test"
    r = s.post(f"{BASE}/api/users",
               json={"email": staff_email, "name": "Staff C", "role": "consultant",
                     "password": "StaffPass2026!"}, timeout=30)
    assert r.status_code == 200, f"create staff -> {r.status_code} {r.text}"
    staff = r.json()
    staff_uid = staff["id"]

    # Directly insert a staff-owned client + asset via pymongo
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    staff_client_id = str(uuid.uuid4())
    db.clients.insert_one({
        "id": staff_client_id, "tenant_id": tid, "client_type": "individual",
        "name": "Staff顧客", "consultant_id": staff_uid,
        "created_at": now_iso, "updated_at": now_iso,
        "created_by": staff_uid, "updated_by": staff_uid,
    })
    staff_asset_id = str(uuid.uuid4())
    db.assets.insert_one({
        "id": staff_asset_id, "tenant_id": tid, "client_id": staff_client_id,
        "asset_class": "stock", "name": "STAFF_STOCK", "currency": "JPY",
        "quantity": 10, "current_price": 100,
        "created_at": now_iso, "updated_at": now_iso,
    })

    return {
        "a": consultant_a,
        "a_client_id": a_client["id"],
        "staff_uid": staff_uid,
        "staff_email": staff_email,
        "staff_password": "StaffPass2026!",
        "staff_client_id": staff_client_id,
        "staff_asset_id": staff_asset_id,
    }


# ---------- Tests ----------

def test_a_lists_only_own_client(env):
    s = env["a"]["session"]
    r = s.get(f"{BASE}/api/data/clients", timeout=30)
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert env["a_client_id"] in ids
    assert env["staff_client_id"] not in ids, "Consultant A must NOT see staff's client"


def test_a_assets_excludes_staff_client_asset(env):
    s = env["a"]["session"]
    r = s.get(f"{BASE}/api/data/assets", timeout=30)
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert env["staff_asset_id"] not in ids, "Staff's asset must be hidden from A"


def test_a_cannot_get_staff_client_dashboard(env):
    s = env["a"]["session"]
    r = s.get(f"{BASE}/api/analytics/dashboard",
              params={"client_id": env["staff_client_id"]}, timeout=30)
    assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"


def test_a_cannot_get_staff_client_by_id(env):
    s = env["a"]["session"]
    r = s.get(f"{BASE}/api/data/clients/{env['staff_client_id']}", timeout=30)
    # Either 403 or 404 (filtered out) is acceptable isolation
    assert r.status_code in (403, 404), f"got {r.status_code} {r.text[:200]}"


def test_a_cannot_update_staff_client(env):
    s = env["a"]["session"]
    r = s.put(f"{BASE}/api/data/clients/{env['staff_client_id']}",
              json={"name": "hacked"}, timeout=30)
    assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"


def test_a_cannot_delete_staff_client(env):
    s = env["a"]["session"]
    r = s.delete(f"{BASE}/api/data/clients/{env['staff_client_id']}", timeout=30)
    assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"


def test_a_cannot_create_client_assigned_to_staff(env):
    s = env["a"]["session"]
    r = s.post(f"{BASE}/api/data/clients",
               json={"client_type": "individual", "name": "hack",
                     "consultant_id": env["staff_uid"]}, timeout=30)
    assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"


def test_staff_sees_only_its_own_client(env):
    s = _login(env["staff_email"], env["staff_password"])
    r = s.get(f"{BASE}/api/data/clients", timeout=30)
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert ids == [env["staff_client_id"]], f"staff should only see its own client, got {ids}"


# ---------- Regression: preview demo tenant ----------

def test_finora_admin_sees_all_tenant_clients():
    s = _login("ryuichi.kurozaki@gmail.com", "Finora2026!")
    me = s.get(f"{BASE}/api/auth/me", timeout=30).json()
    assert me["role"] == "admin"
    assert not me.get("is_consultant"), "ryuichi is FINORA admin, not is_consultant"
    r = s.get(f"{BASE}/api/data/clients", timeout=30)
    assert r.status_code == 200
    clients = r.json()
    assert len(clients) >= 4, f"FINORA admin should see 4+ demo clients, got {len(clients)}"


def test_preview_consultant_sees_only_assigned():
    s = _login("consultant@finora.co.jp", "Finora2026!")
    me = s.get(f"{BASE}/api/auth/me", timeout=30).json()
    assert me["role"] == "consultant"
    r = s.get(f"{BASE}/api/data/clients", timeout=30)
    assert r.status_code == 200
    names = sorted([c.get("name") or c.get("corporate_name") for c in r.json()])
    expected = sorted(["佐藤 健一", "ノヴァテック", "Ana Paula Ferreira"])
    assert names == expected, f"expected {expected}, got {names}"


def test_preview_client_sees_only_self():
    s = _login("client@finora.co.jp", "Finora2026!")
    me = s.get(f"{BASE}/api/auth/me", timeout=30).json()
    assert me["role"] == "client"
    r = s.get(f"{BASE}/api/data/clients", timeout=30)
    assert r.status_code == 200
    clients = r.json()
    assert len(clients) == 1, f"client should see 1 client, got {len(clients)}"
    assert (clients[0].get("name") or clients[0].get("corporate_name")) == "佐藤 健一"
