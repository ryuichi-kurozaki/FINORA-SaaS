"""Iter26: meetings request_id link, ICS, minutes DRAFT/APPROVE flow."""
import asyncio
import os
import time
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

CONS = ("consultant@finora.co.jp", "Finora2026!")
CLIENT = ("client@finora.co.jp", "Finora2026!")
CONSB = ("consultantb@finora.co.jp", "Finora2026!")
ADMIN = ("ryuichi.kurozaki@gmail.com", "Finora2026!")

CLIENT_ID = "56f42e4d-01c3-49a3-904b-6c91642a5167"
REQUEST_ID = "c00c5db3-1771-4e6c-b112-2dab5961ea0a"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def cons():
    return _login(*CONS)


@pytest.fixture(scope="module")
def cli():
    return _login(*CLIENT)


@pytest.fixture(scope="module")
def consb():
    return _login(*CONSB)


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def mongo():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ---------- request_id linkage ----------
class TestRequestLink:
    def test_create_with_request_updates_request(self, cons, mongo):
        scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 3600))
        r = cons.post(f"{API}/meetings", json={
            "client_id": CLIENT_ID, "title": "TEST_reqbook", "scheduled_at": scheduled,
            "duration_min": 45, "request_id": REQUEST_ID,
        }, timeout=15)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["request_id"] == REQUEST_ID

        # verify request updated
        doc = _run(mongo.requests.find_one({"id": REQUEST_ID}))
        assert doc["video_meeting_id"] == m["id"]
        assert doc["video_meeting_at"] == scheduled

        # cancel -> unset on request
        r = cons.post(f"{API}/meetings/{m['id']}/cancel", timeout=15)
        assert r.status_code == 200
        doc = _run(mongo.requests.find_one({"id": REQUEST_ID}))
        assert "video_meeting_id" not in doc
        assert "video_meeting_at" not in doc

    def test_request_from_other_client_404(self, cons, mongo):
        # find any request belonging to a different client in same tenant
        other = _run(mongo.requests.find_one({"tenant_id": {"$exists": True}, "client_id": {"$ne": CLIENT_ID}}))
        if not other:
            pytest.skip("no other-client request found")
        scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 3600))
        r = cons.post(f"{API}/meetings", json={
            "client_id": CLIENT_ID, "title": "TEST_wrongreq", "scheduled_at": scheduled,
            "duration_min": 30, "request_id": other["id"],
        }, timeout=15)
        assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text}"


# ---------- ICS generation ----------
class TestICS:
    def test_ics_content(self, cons, mongo):
        # Import the _ics helper directly
        import sys
        sys.path.insert(0, "/app/backend")
        from meetings import _ics  # noqa

        scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 3600))
        r = cons.post(f"{API}/meetings", json={
            "client_id": CLIENT_ID, "title": "TEST_ics_meeting", "scheduled_at": scheduled, "duration_min": 30,
        }, timeout=15)
        assert r.status_code == 200
        m = r.json()

        req = _ics(m, "REQUEST", "client@finora.co.jp")
        assert "METHOD:REQUEST" in req
        assert f"UID:{m['id']}@finora.co.jp" in req
        assert "SEQUENCE:0" in req
        assert "STATUS:CONFIRMED" in req
        assert "BEGIN:VCALENDAR" in req and "END:VCALENDAR" in req

        cnc = _ics(m, "CANCEL", "client@finora.co.jp")
        assert "METHOD:CANCEL" in cnc
        assert "SEQUENCE:1" in cnc
        assert "STATUS:CANCELLED" in cnc

        # cleanup
        cons.post(f"{API}/meetings/{m['id']}/cancel", timeout=15)

    def test_email_log_both_client_and_consultant(self, cons, admin):
        # Book a meeting and check email_log has entries for BOTH client email and consultant email
        # Use a unique scheduled_at minute so we can locate the entries by subject
        ts = int(time.time()) + 3600
        scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(ts))
        r = cons.post(f"{API}/meetings", json={
            "client_id": CLIENT_ID, "title": "TEST_email_both", "scheduled_at": scheduled, "duration_min": 30,
        }, timeout=15)
        assert r.status_code == 200
        m = r.json()
        time.sleep(3)  # allow async _deliver

        # search subject by scheduled time marker (JST)
        from datetime import datetime, timezone, timedelta
        jst = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(timezone(timedelta(hours=9)))
        marker = jst.strftime("%Y-%m-%d %H:%M")

        r = admin.get(f"{API}/platform/email-log?kind=meeting&limit=50", timeout=15)
        assert r.status_code == 200
        rows = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        matching = [x for x in rows if marker in x.get("subject", "") and "予約" in x.get("subject", "")]
        emails = {x.get("to") for x in matching}
        assert "client@finora.co.jp" in emails, f"client email missing: {emails}"
        assert "consultant@finora.co.jp" in emails, f"consultant email missing: {emails}"

        cons.post(f"{API}/meetings/{m['id']}/cancel", timeout=15)


# ---------- Minutes flow ----------
@pytest.fixture(scope="module")
def minutes_meeting(cons, mongo):
    scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 3600))
    r = cons.post(f"{API}/meetings", json={
        "client_id": CLIENT_ID, "title": "TEST_minutes_flow", "scheduled_at": scheduled, "duration_min": 30,
    }, timeout=15)
    assert r.status_code == 200
    m = r.json()
    # simulate AI output -> DRAFT with minutes+transcript
    _run(mongo.meetings.update_one({"id": m["id"]}, {"$set": {
        "minutes_status": "DRAFT", "minutes": "テスト議事録", "transcript": "文字起こし",
    }}))
    yield m
    # cleanup
    _run(mongo.meetings.delete_one({"id": m["id"]}))


class TestMinutesRBAC:
    def test_client_get_hides_minutes_and_transcript(self, cli, minutes_meeting):
        r = cli.get(f"{API}/meetings", timeout=15)
        assert r.status_code == 200
        m = next(x for x in r.json() if x["id"] == minutes_meeting["id"])
        assert "minutes" not in m
        assert "transcript" not in m
        assert "minutes_error" not in m
        assert "minutes_approved" not in m  # not yet approved

    def test_client_cannot_edit_or_approve_or_transcript(self, cli, minutes_meeting):
        mid = minutes_meeting["id"]
        r = cli.put(f"{API}/meetings/{mid}/minutes", json={"text": "hacked"}, timeout=15)
        assert r.status_code == 403
        r = cli.post(f"{API}/meetings/{mid}/minutes/approve", timeout=15)
        assert r.status_code == 403
        r = cli.get(f"{API}/meetings/{mid}/transcript", timeout=15)
        assert r.status_code == 403

    def test_staff_transcript(self, cons, minutes_meeting):
        r = cons.get(f"{API}/meetings/{minutes_meeting['id']}/transcript", timeout=15)
        assert r.status_code == 200
        assert r.json()["transcript"] == "文字起こし"

    def test_edit_keeps_draft(self, cons, mongo, minutes_meeting):
        mid = minutes_meeting["id"]
        r = cons.put(f"{API}/meetings/{mid}/minutes", json={"text": "編集済み議事録"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["minutes_status"] == "DRAFT"
        doc = _run(mongo.meetings.find_one({"id": mid}))
        assert doc["minutes"] == "編集済み議事録"
        assert doc["minutes_status"] == "DRAFT"

    def test_approve_and_notify(self, cons, cli, admin, mongo, minutes_meeting):
        mid = minutes_meeting["id"]
        r = cons.post(f"{API}/meetings/{mid}/minutes/approve", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["minutes_status"] == "APPROVED"

        doc = _run(mongo.meetings.find_one({"id": mid}))
        assert doc["minutes_status"] == "APPROVED"
        assert doc["minutes_approved"] == "編集済み議事録"

        # client sees approved
        r = cli.get(f"{API}/meetings", timeout=15)
        m = next(x for x in r.json() if x["id"] == mid)
        assert m.get("minutes_approved") == "編集済み議事録"
        assert "minutes" not in m
        assert "transcript" not in m

        time.sleep(2)
        # client in-app notif meeting_minutes
        r = cli.get(f"{API}/notifications", timeout=15)
        notifs = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        kinds = [n.get("kind") for n in notifs]
        assert "meeting_minutes" in kinds, f"kinds={kinds[:10]}"

        # email_log entry
        r = admin.get(f"{API}/platform/email-log?kind=meeting", timeout=15)
        rows = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        found = any("TEST_minutes_flow" in (x.get("subject", "") + x.get("body", "")) and "議事録" in x.get("subject", "") for x in rows)
        assert found, "no minutes email in email_log"

    def test_approve_when_not_draft_409(self, cons, minutes_meeting):
        # currently APPROVED, approve again -> 409
        r = cons.post(f"{API}/meetings/{minutes_meeting['id']}/minutes/approve", timeout=15)
        assert r.status_code == 409

    def test_edit_after_approve_returns_to_draft_client_sees_old(self, cons, cli, mongo, minutes_meeting):
        mid = minutes_meeting["id"]
        r = cons.put(f"{API}/meetings/{mid}/minutes", json={"text": "新しい編集中"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["minutes_status"] == "DRAFT"
        # client still sees previously approved
        r = cli.get(f"{API}/meetings", timeout=15)
        m = next(x for x in r.json() if x["id"] == mid)
        assert m.get("minutes_approved") == "編集済み議事録"

    def test_edit_fails_when_processing_or_failed_or_none(self, cons, mongo, minutes_meeting):
        mid = minutes_meeting["id"]
        # set PROCESSING
        _run(mongo.meetings.update_one({"id": mid}, {"$set": {"minutes_status": "PROCESSING"}}))
        r = cons.put(f"{API}/meetings/{mid}/minutes", json={"text": "x"}, timeout=15)
        assert r.status_code == 409
        # set FAILED
        _run(mongo.meetings.update_one({"id": mid}, {"$set": {"minutes_status": "FAILED"}}))
        r = cons.put(f"{API}/meetings/{mid}/minutes", json={"text": "x"}, timeout=15)
        assert r.status_code == 409
        # unset
        _run(mongo.meetings.update_one({"id": mid}, {"$unset": {"minutes_status": ""}}))
        r = cons.put(f"{API}/meetings/{mid}/minutes", json={"text": "x"}, timeout=15)
        assert r.status_code == 409


def teardown_module(module):
    """Clean TEST_ meetings and reset request video fields."""
    async def _clean():
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not (mongo_url and db_name):
            return
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        await db.meetings.delete_many({"title": {"$regex": "^TEST_"}})
        await db.requests.update_many({"id": REQUEST_ID}, {"$unset": {"video_meeting_id": "", "video_meeting_at": ""}})
    try:
        _run(_clean())
    except Exception as e:
        print(f"cleanup skipped: {e}")
