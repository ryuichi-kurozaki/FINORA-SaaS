"""Tests for the e-contract renewal/expiry notice feature (POST /api/econtracts/renewals/run + persistence + idempotency)."""
import os
import sys
from datetime import date, timedelta

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": "ryuichi.kurozaki@gmail.com", "password": "Finora2026!"}
CONS = {"email": "consultant@finora.co.jp", "password": "Finora2026!"}
TARGET_NUMBER = "CC-00003"  # ACTIVE consulting econtract to override


def _login(s, cred):
    r = s.post(f"{BASE_URL}/api/auth/login", json=cred, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, ADMIN)
    yield s
    s.close()


@pytest.fixture(scope="module")
def cons_session():
    s = requests.Session()
    _login(s, CONS)
    yield s
    s.close()


@pytest.fixture(scope="module")
def target_contract(admin_session):
    """Find CC-00003, patch its terms.end_date to ~20 days out via direct mongo write, snapshot for restore."""
    from motor.motor_asyncio import AsyncIOMotorClient
    import asyncio
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    async def snapshot():
        c = await mongo.econtracts.find_one({"number": TARGET_NUMBER, "status": "ACTIVE"})
        return c

    async def restore(orig_end):
        await mongo.econtracts.update_one({"number": TARGET_NUMBER}, {"$set": {"terms.end_date": orig_end}})

    c = asyncio.get_event_loop().run_until_complete(snapshot())
    assert c, f"{TARGET_NUMBER} ACTIVE contract not found"
    orig_end = c["terms"].get("end_date")
    yield c
    asyncio.get_event_loop().run_until_complete(restore(orig_end))


# ---- endpoint auth ----
def test_run_requires_platform_admin(cons_session):
    r = cons_session.post(f"{BASE_URL}/api/econtracts/renewals/run", timeout=15)
    assert r.status_code == 403


def test_run_platform_admin_ok(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/econtracts/renewals/run", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "sent" in j and isinstance(j["sent"], list)


# ---- econtract row exposes renew_on / renew_days ----
def test_list_and_detail_have_renew_fields(admin_session, target_contract):
    cid = target_contract["id"]
    r = admin_session.get(f"{BASE_URL}/api/econtracts/{cid}", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "renew_on" in d and "renew_days" in d
    # For CC-00003 (open-ended auto_renew, start 2026-02-01) renew_on should be a future ISO date or null
    if d["renew_on"]:
        assert len(d["renew_on"]) == 10  # ISO
        assert isinstance(d["renew_days"], int)


# ---- stage/idempotency using time-travel via ?today= ----
def test_stage30_then_stage7_then_dedupe(admin_session, target_contract):
    from motor.motor_asyncio import AsyncIOMotorClient
    import asyncio
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    cid = target_contract["id"]

    # Compute renew_on from current terms (open-ended auto_renew => yearly anniversary of start_date)
    r = admin_session.get(f"{BASE_URL}/api/econtracts/{cid}", timeout=15)
    d = r.json()
    renew_on = d["renew_on"]
    assert renew_on, "contract has no renew_on (expected for open-ended auto_renew)"
    ro = date.fromisoformat(renew_on)

    # Cleanup any stale rows for this contract+renew_on
    async def cleanup():
        await mongo.renewal_notices.delete_many({"contract_id": cid, "renew_on": renew_on})
        await mongo.notifications.delete_many({"kind": "econtract_renewal_notice"})
        await mongo.message_log.delete_many({"kind": "econtract_renewal_notice"})
    asyncio.get_event_loop().run_until_complete(cleanup())

    # ---- Stage 30 (27 days out) ----
    t30 = (ro - timedelta(days=27)).isoformat()
    r1 = admin_session.post(f"{BASE_URL}/api/econtracts/renewals/run?today={t30}", timeout=30).json()
    hits = [x for x in r1["sent"] if x["contract_id"] == cid]
    assert len(hits) == 1, f"expected 1 stage-30 send, got {hits}"
    assert hits[0]["stage"] == 30
    assert hits[0]["days"] == 27
    assert hits[0]["renew_on"] == renew_on

    # ---- Idempotency: same day again ----
    r2 = admin_session.post(f"{BASE_URL}/api/econtracts/renewals/run?today={t30}", timeout=30).json()
    assert [x for x in r2["sent"] if x["contract_id"] == cid] == [], "should NOT resend stage 30"

    # ---- Next day still stage 30, still dedup ----
    t30b = (ro - timedelta(days=26)).isoformat()
    r3 = admin_session.post(f"{BASE_URL}/api/econtracts/renewals/run?today={t30b}", timeout=30).json()
    assert [x for x in r3["sent"] if x["contract_id"] == cid] == []

    # ---- Stage 7 (5 days out) ----
    t7 = (ro - timedelta(days=5)).isoformat()
    r4 = admin_session.post(f"{BASE_URL}/api/econtracts/renewals/run?today={t7}", timeout=30).json()
    hits7 = [x for x in r4["sent"] if x["contract_id"] == cid]
    assert len(hits7) == 1
    assert hits7[0]["stage"] == 7
    assert hits7[0]["days"] == 5

    # ---- Dedupe stage 7 ----
    r5 = admin_session.post(f"{BASE_URL}/api/econtracts/renewals/run?today={t7}", timeout=30).json()
    assert [x for x in r5["sent"] if x["contract_id"] == cid] == []

    # ---- >30 days: nothing ----
    t_far = (ro - timedelta(days=60)).isoformat()
    r6 = admin_session.post(f"{BASE_URL}/api/econtracts/renewals/run?today={t_far}", timeout=30).json()
    assert [x for x in r6["sent"] if x["contract_id"] == cid] == []

    # ---- Verify notifications + message_log side effects were created ----
    async def check_side_effects():
        notif = await mongo.notifications.count_documents({"kind": "econtract_renewal_notice"})
        mlog = await mongo.message_log.count_documents({"kind": "econtract_renewal_notice", "contract_id": cid})
        return notif, mlog
    notif, mlog = asyncio.get_event_loop().run_until_complete(check_side_effects())
    assert notif >= 2, f"expected >= 2 in-app notifications, got {notif}"
    assert mlog >= 2, f"expected >= 2 message_log rows, got {mlog}"

    # ---- final cleanup so main-agent DB is clean ----
    async def final_cleanup():
        await mongo.renewal_notices.delete_many({"contract_id": cid})
        await mongo.notifications.delete_many({"kind": "econtract_renewal_notice"})
        await mongo.message_log.delete_many({"kind": "econtract_renewal_notice"})
    asyncio.get_event_loop().run_until_complete(final_cleanup())


# ---- renew_on math for the 4 scenarios ----
def test_renew_on_matrix():
    from econtract import renew_on
    today = date(2027, 1, 5)
    base = {"status": "ACTIVE", "terms": {"start_date": "2026-02-01", "auto_renew": True}}
    # open-ended + auto_renew -> next anniversary after today
    assert renew_on(base, today) == date(2027, 2, 1)
    # end_date + auto_renew -> rolled forward until >= today
    c2 = {"status": "ACTIVE", "terms": {"start_date": "2020-02-01", "end_date": "2022-02-01", "auto_renew": True}}
    assert renew_on(c2, today) == date(2027, 2, 1)
    # end_date + auto_renew false -> end_date if >= today else None
    c3 = {"status": "ACTIVE", "terms": {"start_date": "2020-02-01", "end_date": "2027-06-01", "auto_renew": False}}
    assert renew_on(c3, today) == date(2027, 6, 1)
    c4 = {"status": "ACTIVE", "terms": {"start_date": "2020-02-01", "end_date": "2020-06-01", "auto_renew": False}}
    assert renew_on(c4, today) is None
    # open-ended + auto_renew false -> None
    c5 = {"status": "ACTIVE", "terms": {"start_date": "2026-02-01", "auto_renew": False}}
    assert renew_on(c5, today) is None
    # non-ACTIVE -> None
    c6 = {"status": "DRAFT", "terms": {"start_date": "2026-02-01", "auto_renew": True}}
    assert renew_on(c6, today) is None
