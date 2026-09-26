"""Backend tests for Finora Email Delivery Log (mail_log.py) and integration with email_service._record."""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://investment-hub-309.preview.emergentagent.com"
API = f"{BASE}/api"
MAIL_LOG = "/tmp/finora_mail.log"

ADMIN = ("ryuichi.kurozaki@gmail.com", "Finora2026!")
CONSULTANT = ("consultant@finora.co.jp", "Finora2026!")
TENANT_B = ("consultantb@finora.co.jp", "Finora2026!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


@pytest.fixture(scope="module")
def consultant_h():
    return {"Authorization": f"Bearer {_login(*CONSULTANT)}"}


@pytest.fixture(scope="module")
def tenantb_h():
    return {"Authorization": f"Bearer {_login(*TENANT_B)}"}


@pytest.fixture(scope="module")
def db():
    c = MongoClient("mongodb://localhost:27017")
    return c["test_database"]


# ---------- AuthZ ----------
def test_list_forbidden_for_consultant(consultant_h):
    r = requests.get(f"{API}/platform/email-log", headers=consultant_h, timeout=15)
    assert r.status_code == 403


def test_list_forbidden_for_tenantb_owner(tenantb_h):
    r = requests.get(f"{API}/platform/email-log", headers=tenantb_h, timeout=15)
    assert r.status_code == 403


def test_sync_forbidden_for_consultant(consultant_h):
    r = requests.post(f"{API}/platform/email-log/sync", headers=consultant_h, timeout=15)
    assert r.status_code == 403


def test_list_ok_for_platform_admin(admin_h):
    r = requests.get(f"{API}/platform/email-log", headers=admin_h, timeout=15)
    assert r.status_code == 200
    body = r.json()
    for k in ("items", "total", "counts", "tracking", "synced_at"):
        assert k in body
    assert isinstance(body["items"], list)
    # no mongo _id leak
    for it in body["items"]:
        assert "_id" not in it


# ---------- Filter/search ----------
def test_search_and_kind_filter(admin_h, db):
    # Insert a unique row directly for deterministic search
    uid = uuid.uuid4().hex[:8]
    to = f"TEST_search_{uid}@example.com"
    subj = f"TEST_SUBJECT_{uid}"
    doc = {"id": f"TEST_{uid}", "to": to, "subject": subj, "kind": "invite",
           "message_id": f"msg-{uid}", "queue_id": None, "status": "logged",
           "detail": "", "at": "2026-01-10T00:00:00+00:00", "updated_at": "2026-01-10T00:00:00+00:00"}
    db.email_log.insert_one(doc)
    try:
        # q matches recipient (case-insensitive)
        r = requests.get(f"{API}/platform/email-log", headers=admin_h, params={"q": f"SEARCH_{uid}"}, timeout=15)
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["items"]]
        assert doc["id"] in ids

        # q matches subject
        r = requests.get(f"{API}/platform/email-log", headers=admin_h, params={"q": f"subject_{uid}"}, timeout=15)
        assert r.status_code == 200
        assert doc["id"] in [i["id"] for i in r.json()["items"]]

        # kind filter matches
        r = requests.get(f"{API}/platform/email-log", headers=admin_h, params={"q": uid, "kind": "invite"}, timeout=15)
        assert doc["id"] in [i["id"] for i in r.json()["items"]]
        # kind filter mismatch
        r = requests.get(f"{API}/platform/email-log", headers=admin_h, params={"q": uid, "kind": "invoice"}, timeout=15)
        assert doc["id"] not in [i["id"] for i in r.json()["items"]]

        # counts ignore status filter but respect other filters
        r = requests.get(f"{API}/platform/email-log", headers=admin_h, params={"q": uid, "status": "delivered"}, timeout=15)
        body = r.json()
        # our row is 'logged' so with status=delivered, items excludes it but counts.logged should include it
        assert doc["id"] not in [i["id"] for i in body["items"]]
        assert body["counts"].get("logged", 0) >= 1
    finally:
        db.email_log.delete_one({"id": doc["id"]})


def test_pagination(admin_h):
    r = requests.get(f"{API}/platform/email-log", headers=admin_h, params={"limit": 1}, timeout=15)
    assert r.status_code == 200
    j1 = r.json()
    assert len(j1["items"]) <= 1
    if j1["total"] > 1:
        r2 = requests.get(f"{API}/platform/email-log", headers=admin_h, params={"limit": 1, "skip": 1}, timeout=15)
        assert r2.status_code == 200
        j2 = r2.json()
        if j1["items"] and j2["items"]:
            assert j1["items"][0]["id"] != j2["items"][0]["id"]


def test_sorted_newest_first(admin_h):
    r = requests.get(f"{API}/platform/email-log", headers=admin_h, params={"limit": 20}, timeout=15)
    items = r.json()["items"]
    ats = [i["at"] for i in items if i.get("at")]
    assert ats == sorted(ats, reverse=True)


# ---------- Postfix sync ----------
def _append(lines):
    with open(MAIL_LOG, "a") as f:
        for ln in lines:
            f.write(ln + "\n")


def test_sync_delivered_deferred_bounced_expired(admin_h, db):
    uid = uuid.uuid4().hex[:6]
    rows = []
    for status_target, postfix_status in [("delivered", "sent"), ("deferred", "deferred"), ("bounced", "bounced")]:
        mid = f"m-{uid}-{status_target}@x"
        qid = f"Q{uid}{status_target[:3].upper()}"
        rid = f"TEST_{uid}_{status_target}"
        db.email_log.insert_one({"id": rid, "to": f"x_{uid}_{status_target}@y.com", "subject": f"s {status_target}",
                                 "kind": "system", "message_id": mid, "queue_id": None, "status": "queued",
                                 "detail": "", "at": "2026-01-10T00:00:00+00:00", "updated_at": "2026-01-10T00:00:00+00:00"})
        rows.append((rid, qid, mid, status_target, postfix_status))

    # Also test 'expired -> bounced' via qmgr line
    mid_e = f"m-{uid}-exp@x"
    qid_e = f"Q{uid}EXP"
    rid_e = f"TEST_{uid}_expired"
    db.email_log.insert_one({"id": rid_e, "to": f"x_{uid}_exp@y.com", "subject": "s exp", "kind": "system",
                             "message_id": mid_e, "queue_id": None, "status": "queued", "detail": "",
                             "at": "2026-01-10T00:00:00+00:00", "updated_at": "2026-01-10T00:00:00+00:00"})

    try:
        lines = []
        for _, qid, mid, _, pstatus in rows:
            lines.append(f"Jan 10 10:00:00 h postfix/cleanup[1]: {qid}: message-id=<{mid}>")
            lines.append(f"Jan 10 10:00:01 h postfix/smtp[2]: {qid}: to=<recipient@y.com>, relay=x, delay=1, delays=0/0/0/1, dsn=2.0.0, status={pstatus} (250 OK)")
        lines.append(f"Jan 10 10:00:02 h postfix/cleanup[1]: {qid_e}: message-id=<{mid_e}>")
        lines.append(f"Jan 10 10:00:03 h postfix/qmgr[1]: {qid_e}: from=<x@y.com>, status=expired, returned to sender")
        _append(lines)

        r = requests.post(f"{API}/platform/email-log/sync", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["enabled"] is True
        assert body["updated"] >= 4

        for rid, qid, mid, target, _ in rows:
            row = db.email_log.find_one({"id": rid})
            assert row["queue_id"] == qid, f"{rid} queue_id"
            assert row["status"] == target, f"{rid}: expected {target}, got {row['status']}"

        row = db.email_log.find_one({"id": rid_e})
        assert row["queue_id"] == qid_e
        assert row["status"] == "bounced"

        # Second sync must not re-read old lines
        r2 = requests.post(f"{API}/platform/email-log/sync", headers=admin_h, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["updated"] == 0
    finally:
        db.email_log.delete_many({"id": {"$regex": f"^TEST_{uid}"}})


def test_sync_handles_truncation(admin_h, db):
    """If file is truncated (smaller than offset), reading restarts from 0."""
    uid = uuid.uuid4().hex[:6]
    mid = f"m-trunc-{uid}@x"
    qid = f"QTRUNC{uid}"
    rid = f"TEST_trunc_{uid}"
    db.email_log.insert_one({"id": rid, "to": f"trunc_{uid}@y.com", "subject": "trunc", "kind": "system",
                             "message_id": mid, "queue_id": None, "status": "queued", "detail": "",
                             "at": "2026-01-10T00:00:00+00:00", "updated_at": "2026-01-10T00:00:00+00:00"})
    try:
        # Truncate the file entirely (resets offset next sync)
        with open(MAIL_LOG, "w") as f:
            f.write("")

        # First sync to save offset=0
        requests.post(f"{API}/platform/email-log/sync", headers=admin_h, timeout=30)

        # Now append lines
        _append([
            f"Jan 10 10:00:00 h postfix/cleanup[1]: {qid}: message-id=<{mid}>",
            f"Jan 10 10:00:01 h postfix/smtp[2]: {qid}: to=<x@y.com>, relay=x, delay=1, delays=0/0/0/1, dsn=2.0.0, status=sent (250 OK)",
        ])
        r = requests.post(f"{API}/platform/email-log/sync", headers=admin_h, timeout=30)
        assert r.status_code == 200
        assert r.json()["updated"] >= 1

        row = db.email_log.find_one({"id": rid})
        assert row["status"] == "delivered"
    finally:
        db.email_log.delete_many({"id": {"$regex": f"^TEST_trunc_{uid}"}})


# ---------- Inquiry -> kind='inquiry' row ----------
def test_public_inquiry_creates_inquiry_log_row(admin_h, db):
    uid = uuid.uuid4().hex[:6]
    payload = {
        "name": f"TEST Tester {uid}",
        "email": f"test_inq_{uid}@example.com",
        "message": f"Hello this is a test inquiry {uid} - please ignore.",
        "lang": "ja",
    }
    r = requests.post(f"{API}/public/inquiries", json=payload, timeout=20)
    # Endpoint should be publicly accessible
    assert r.status_code in (200, 201, 429), r.text
    if r.status_code == 429:
        pytest.skip("inquiry rate-limited")
    time.sleep(1)
    # Look for an email_log row with kind=inquiry created recently
    row = db.email_log.find_one({"kind": "inquiry"}, sort=[("at", -1)])
    assert row is not None, "no email_log row with kind=inquiry found"
    # message_id must not contain angle brackets
    assert "<" not in (row.get("message_id") or "")
    assert ">" not in (row.get("message_id") or "")
    # In preview EMAIL_TRANSPORT=log => status should be 'logged'
    assert row["status"] in ("logged", "queued")
