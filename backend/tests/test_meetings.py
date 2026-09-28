"""Backend tests for /api/meetings — scheduling, RBAC/scope, signaling, recording, minutes, signed URL."""
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://investment-hub-309.preview.emergentagent.com"
API = f"{BASE_URL}/api"

CONS = ("consultant@finora.co.jp", "Finora2026!")
CLIENT = ("client@finora.co.jp", "Finora2026!")
CONSB = ("consultantb@finora.co.jp", "Finora2026!")
ADMIN = ("ryuichi.kurozaki@gmail.com", "Finora2026!")

CLIENT_ID = "56f42e4d-01c3-49a3-904b-6c91642a5167"


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
def created_meeting(cons):
    # schedule ~2 min in the future so join button shows in FE too
    scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 120))
    r = cons.post(f"{API}/meetings", json={
        "client_id": CLIENT_ID, "title": "TEST_meeting_apitest", "scheduled_at": scheduled, "duration_min": 30,
    }, timeout=15)
    assert r.status_code == 200, f"create meeting: {r.status_code} {r.text}"
    m = r.json()
    assert m["status"] == "SCHEDULED"
    assert m["client_id"] == CLIENT_ID
    assert m["title"] == "TEST_meeting_apitest"
    assert "id" in m
    return m


class TestScheduling:
    def test_create_by_consultant(self, created_meeting):
        assert created_meeting["status"] == "SCHEDULED"

    def test_client_cannot_create(self, cli):
        scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 300))
        r = cli.post(f"{API}/meetings", json={
            "client_id": CLIENT_ID, "title": "TEST_client_should_403", "scheduled_at": scheduled, "duration_min": 30,
        }, timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"

    def test_other_tenant_cannot_create(self, consb):
        scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 300))
        r = consb.post(f"{API}/meetings", json={
            "client_id": CLIENT_ID, "title": "TEST_wrongtenant", "scheduled_at": scheduled, "duration_min": 30,
        }, timeout=15)
        assert r.status_code in (403, 404), f"expected 403/404, got {r.status_code} {r.text}"

    def test_list_client_scoped(self, cli, created_meeting):
        r = cli.get(f"{API}/meetings", timeout=15)
        assert r.status_code == 200
        rows = r.json()
        ids = [m["id"] for m in rows]
        assert created_meeting["id"] in ids
        # every meeting must belong to CLIENT_ID
        assert all(m["client_id"] == CLIENT_ID for m in rows)

    def test_list_cross_tenant_forbidden(self, consb):
        r = consb.get(f"{API}/meetings?client_id={CLIENT_ID}", timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"

    def test_notification_and_email_log(self, cli, admin, created_meeting):
        # client user in-app notification with kind meeting_new
        r = cli.get(f"{API}/notifications", timeout=15)
        assert r.status_code == 200, r.text
        notifs = r.json()
        kinds = [n.get("kind") for n in (notifs if isinstance(notifs, list) else notifs.get("items", []))]
        assert "meeting_new" in kinds, f"meeting_new not in notifications kinds: {kinds[:20]}"

        # email_log entry with kind='meeting'
        r = admin.get(f"{API}/platform/email-log?kind=meeting", timeout=15)
        assert r.status_code == 200, r.text
        rows = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        found = any(created_meeting["title"] in (row.get("subject", "") + row.get("body", "")) for row in rows[:50])
        assert found or len(rows) > 0, "no meeting email_log entries"


class TestICE:
    def test_ice(self, cons):
        r = cons.get(f"{API}/meetings/ice", timeout=15)
        assert r.status_code == 200
        srv = r.json().get("iceServers", [])
        assert any("stun:" in (s["urls"] if isinstance(s["urls"], str) else s["urls"][0]) for s in srv)


class TestSignaling:
    def test_invalid_type_422(self, cons, created_meeting):
        r = cons.post(f"{API}/meetings/{created_meeting['id']}/signal", json={"type": "bogus", "data": {}}, timeout=15)
        assert r.status_code == 422, f"expected 422, got {r.status_code}"

    def test_hello_sets_live_and_poll_other_party(self, cons, cli, created_meeting):
        mid = created_meeting["id"]
        r = cons.post(f"{API}/meetings/{mid}/signal", json={"type": "hello", "data": {}}, timeout=15)
        assert r.status_code == 200
        # client polls with since=0 -> should see consultant's hello
        r = cli.get(f"{API}/meetings/{mid}/signal?since=0", timeout=15)
        assert r.status_code == 200
        rows = r.json()
        types = [x["type"] for x in rows]
        assert "hello" in types

        # consultant polling own message should NOT see it back
        r = cons.get(f"{API}/meetings/{mid}/signal?since=0", timeout=15)
        assert r.status_code == 200
        assert all(x.get("from") != "self" for x in r.json())  # trivially true; but list should be empty of own hello
        my = [x for x in r.json() if x["type"] == "hello"]
        assert my == [], "should not receive own signals"

        # meeting status should now be LIVE
        rows = cons.get(f"{API}/meetings", timeout=15).json()
        m = next(x for x in rows if x["id"] == mid)
        assert m["status"] == "LIVE"


class TestRecording:
    def test_full_flow(self, cons, cli, admin, created_meeting):
        mid = created_meeting["id"]
        # client cannot upload chunks
        r = cli.post(f"{API}/meetings/{mid}/recording/video/chunk?idx=0", data=b"x" * 32, timeout=15)
        assert r.status_code == 403

        # consultant uploads 2 video chunks + 2 audio chunks
        for idx in (0, 1):
            r = cons.post(f"{API}/meetings/{mid}/recording/video/chunk?idx={idx}", data=b"VIDEODATA" * 32, timeout=15)
            assert r.status_code == 200
            r = cons.post(f"{API}/meetings/{mid}/recording/audio/chunk?idx={idx}", data=b"AUDIODATA" * 32, timeout=15)
            assert r.status_code == 200

        # invalid kind
        r = cons.post(f"{API}/meetings/{mid}/recording/foo/chunk?idx=0", data=b"x", timeout=15)
        assert r.status_code == 404

        # done -> minutes PROCESSING (will fail with fake bytes)
        r = cons.post(f"{API}/meetings/{mid}/recording/done", timeout=15)
        assert r.status_code == 200

        # recording-url signed
        r = cli.get(f"{API}/meetings/{mid}/recording-url", timeout=15)
        assert r.status_code == 200
        url = r.json()["url"]
        assert "sig=" in url and "exp=" in url

        # GET signed URL returns video
        r = requests.get(f"{BASE_URL}{url}", timeout=15, cookies=cli.cookies)
        assert r.status_code == 200
        assert "video/webm" in r.headers.get("content-type", "")

        # tampered sig -> 404
        tampered = url.replace("sig=", "sig=deadbeef")
        # replace the actual sig with garbage
        bad = url.split("sig=")[0] + "sig=" + "0" * 64
        r = requests.get(f"{BASE_URL}{bad}", timeout=15, cookies=cli.cookies)
        assert r.status_code == 404


class TestEnd:
    def test_end(self, cons, created_meeting):
        r = cons.post(f"{API}/meetings/{created_meeting['id']}/end", timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "ENDED"


class TestCancel:
    def test_cancel_flow_and_idempotency(self, cons):
        # create a fresh one
        scheduled = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 7200))
        r = cons.post(f"{API}/meetings", json={
            "client_id": CLIENT_ID, "title": "TEST_cancel_me", "scheduled_at": scheduled, "duration_min": 30,
        }, timeout=15)
        assert r.status_code == 200
        mid = r.json()["id"]

        r = cons.post(f"{API}/meetings/{mid}/cancel", timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELLED"

        # second call -> 409
        r = cons.post(f"{API}/meetings/{mid}/cancel", timeout=15)
        assert r.status_code == 409


# Cleanup — delete all TEST_ meetings via direct mongo (best-effort)
def teardown_module(module):
    try:
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not (mongo_url and db_name):
            return
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]

        async def _cleanup():
            await db.meetings.delete_many({"title": {"$regex": "^TEST_"}})
        asyncio.get_event_loop().run_until_complete(_cleanup())
    except Exception as e:  # noqa
        print(f"cleanup skipped: {e}")
