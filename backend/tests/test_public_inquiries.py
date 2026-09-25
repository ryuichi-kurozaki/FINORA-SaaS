"""Tests for public inquiries + admin RBAC on /api/inquiries."""
import os
import time
import uuid
import requests
import pytest

from pathlib import Path
_env = Path("/app/frontend/.env").read_text() if Path("/app/frontend/.env").exists() else ""
for line in _env.splitlines():
    if line.startswith("REACT_APP_BACKEND_URL="):
        os.environ.setdefault("REACT_APP_BACKEND_URL", line.split("=", 1)[1].strip())
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = ("ryuichi.kurozaki@gmail.com", "Finora2026!")
CONSULT = ("consultant@finora.co.jp", "Finora2026!")
CLIENT = ("client@finora.co.jp", "Finora2026!")


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


def _payload(**over):
    p = {"name": f"TEST_{uuid.uuid4().hex[:6]}", "email": f"t_{uuid.uuid4().hex[:6]}@example.com",
         "message": "Hello this is a test inquiry", "inquiry_type": "corporate", "lang": "ja",
         "company": "TEST Co"}
    p.update(over)
    return p


def test_create_inquiry_ok():
    r = requests.post(f"{BASE}/api/public/inquiries", json=_payload(), timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True


def test_create_inquiry_invalid_email():
    r = requests.post(f"{BASE}/api/public/inquiries", json=_payload(email="not-an-email"), timeout=15)
    assert r.status_code == 422


def test_create_inquiry_invalid_type():
    r = requests.post(f"{BASE}/api/public/inquiries", json=_payload(inquiry_type="bogus"), timeout=15)
    assert r.status_code == 422


def test_honeypot_silently_ok():
    r = requests.post(f"{BASE}/api/public/inquiries", json=_payload(website="http://spam"), timeout=15)
    assert r.status_code == 200


def test_rbac_consultant_forbidden():
    s = _login(*CONSULT)
    assert s.get(f"{BASE}/api/inquiries").status_code == 403


def test_rbac_client_forbidden():
    s = _login(*CLIENT)
    assert s.get(f"{BASE}/api/inquiries").status_code == 403


def test_admin_list_and_update_status(admin):
    # Create one via public endpoint to guarantee we have a row
    marker = f"TEST_{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE}/api/public/inquiries", json=_payload(name=marker), timeout=15)
    assert r.status_code == 200

    r = admin.get(f"{BASE}/api/inquiries", timeout=15)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list) and len(items) > 0
    mine = [x for x in items if x.get("name") == marker]
    assert mine, "created inquiry not found in admin list"
    iid = mine[0]["id"]
    assert mine[0]["status"] == "new"
    assert "_id" not in mine[0]

    # Update status
    r = admin.put(f"{BASE}/api/inquiries/{iid}", json={"status": "in_progress"}, timeout=15)
    assert r.status_code == 200
    # verify persisted
    items2 = admin.get(f"{BASE}/api/inquiries").json()
    updated = [x for x in items2 if x["id"] == iid][0]
    assert updated["status"] == "in_progress"

    # Invalid status
    r = admin.put(f"{BASE}/api/inquiries/{iid}", json={"status": "bogus"}, timeout=15)
    assert r.status_code == 422

    # Not found
    r = admin.put(f"{BASE}/api/inquiries/nonexistent-id", json={"status": "done"}, timeout=15)
    assert r.status_code == 404


def test_rate_limit_429_last():
    """Must run LAST: spams the endpoint to trigger 5/hr/IP cap."""
    got_429 = False
    for _ in range(8):
        r = requests.post(f"{BASE}/api/public/inquiries", json=_payload(), timeout=15)
        if r.status_code == 429:
            got_429 = True
            break
        time.sleep(0.1)
    assert got_429, "expected a 429 within 8 attempts (rate limit is 5/hr/IP)"
