"""Preview tests for FINORA sign-notify feature (WhatsApp prefs + email notifications on e-contract flow)."""
import os
import re
import time

import pytest
import requests
from pymongo import MongoClient

# Force serial execution because tests mutate the shared client2 user email
pytestmark = pytest.mark.xdist_group("serial")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://investment-hub-309.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
PW = "Finora2026!"
ADMIN = "ryuichi.kurozaki@gmail.com"
CLIENT2 = "client2@finora.co.jp"
SAFE_EMAIL = "delivered@resend.dev"

mongo = MongoClient("mongodb://localhost:27017")
db = mongo["test_database"]


def _login(email, password=PW):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def client2_original_email():
    """Snapshot then restore the client2 user email."""
    orig = db.users.find_one({"email": CLIENT2}) or db.users.find_one({"email": SAFE_EMAIL, "role": "client"})
    assert orig, "client2 user not found"
    yield orig["email"]
    # restore email back to CLIENT2 no matter what
    db.users.update_one({"id": orig["id"]}, {"$set": {"email": CLIENT2}})


# ---------------- Prefs API ---------------- #
class TestPrefsAPI:
    def test_put_valid_and_get_me(self):
        s = _login(CLIENT2)
        r = s.put(f"{API}/auth/preferences", json={"whatsapp_phone": "+81 90-1234-5678", "whatsapp_opt_in": True}, timeout=15)
        assert r.status_code == 200, r.text
        me = s.get(f"{API}/auth/me", timeout=15).json()
        assert me["whatsapp_phone"] == "819012345678", me
        assert me["whatsapp_opt_in"] is True

    def test_put_invalid_number(self):
        s = _login(CLIENT2)
        r = s.put(f"{API}/auth/preferences", json={"whatsapp_phone": "abc", "whatsapp_opt_in": True}, timeout=15)
        assert r.status_code == 422, r.text

    def test_put_empty_phone_forces_optin_false(self):
        s = _login(CLIENT2)
        r = s.put(f"{API}/auth/preferences", json={"whatsapp_phone": "", "whatsapp_opt_in": True}, timeout=15)
        assert r.status_code == 200
        me = s.get(f"{API}/auth/me", timeout=15).json()
        assert (me.get("whatsapp_phone") or "") == ""
        assert me["whatsapp_opt_in"] is False


# ---------------- Notifications e-contract flow ---------------- #
class TestSignNotifyFlow:
    def test_full_flow(self, admin_session, client2_original_email):
        # 1) Login as client2 (current email) then rewrite their email to SAFE_EMAIL
        s_client = _login(CLIENT2)
        me_c = s_client.get(f"{API}/auth/me", timeout=15).json()
        client_user_id = me_c["id"]
        client_client_id = me_c.get("client_id")
        assert client_client_id, "client2 must be linked to a client record"
        db.users.update_one({"id": client_user_id}, {"$set": {"email": SAFE_EMAIL}})

        # 2) Admin creates a CONSULTING e-contract for client2's client
        admin_me = admin_session.get(f"{API}/auth/me", timeout=15).json()
        assert admin_me["tenant_id"]
        payload = {
            "contract_type": "CONSULTING",
            "client_id": client_client_id,
            "lang": "ja",
            "terms": {
                "service_name": "TEST_SignNotify",
                "description": "sign-notify preview test",
                "fee_type": "MONTHLY",
                "fee": 30000,
                "tax_mode": "exclusive",
                "tax_rate": 10,
                "start_date": "2026-02-01",
                "billing_day": 1,
                "payment_terms_days": 30,
                "auto_renew": True,
            },
            "fields": {},
        }
        r = admin_session.post(f"{API}/econtracts", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]

        # 3) send-important → EMAIL SENT to SAFE_EMAIL, no WHATSAPP row
        r = admin_session.post(f"{API}/econtracts/{cid}/send-important", timeout=20)
        assert r.status_code == 200, r.text
        rows = []
        for _ in range(12):
            time.sleep(2)
            rows = list(db.message_log.find({"contract_id": cid, "kind": "econtract_important_sent"}))
            if rows:
                break
        emails = [x for x in rows if x["channel"] == "EMAIL"]
        whats = [x for x in rows if x["channel"] == "WHATSAPP"]
        assert emails, f"no EMAIL row for send-important: {rows}"
        assert emails[0]["to"] == SAFE_EMAIL, emails[0]
        assert emails[0]["status"] == "SENT", emails[0]
        assert not whats, f"WHATSAPP row should not exist in preview: {whats}"

        # 4) admin GET detail → messages[] populated; client GET detail → messages empty
        det_admin = admin_session.get(f"{API}/econtracts/{cid}", timeout=20).json()
        assert any(m["kind"] == "econtract_important_sent" for m in det_admin.get("messages") or []), det_admin.get("messages")

        # client must re-login because email changed → old session still ok since same user_id in cookie; but the login-history won't trigger. Use existing s_client.
        det_client = s_client.get(f"{API}/econtracts/{cid}", timeout=20).json()
        assert (det_client.get("messages") or []) == [], det_client.get("messages")

        # 5) client confirms
        r = s_client.post(f"{API}/econtracts/{cid}/confirm", timeout=20)
        assert r.status_code == 200, r.text

        # Regression: send-agreement is legal here, but send-agreement before confirm should be 409 → covered by TestOrderEnforcement below

        # 6) admin sends agreement → EMAIL row for econtract_agreement_sent
        r = admin_session.post(f"{API}/econtracts/{cid}/send-agreement", timeout=20)
        assert r.status_code == 200, r.text
        rows2 = []
        for _ in range(12):
            time.sleep(2)
            rows2 = list(db.message_log.find({"contract_id": cid, "kind": "econtract_agreement_sent"}))
            if rows2:
                break
        assert any(x["channel"] == "EMAIL" and x["to"] == SAFE_EMAIL for x in rows2), rows2

        # 7) client signs → EMAIL attempted to issuer (ryuichi) for econtract_recipient_signed (status SENT or FAILED both acceptable)
        sign_body = {
            "name": "Ana Paula Ferreira",
            "signature_png": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "agree": True,
        }
        r = s_client.post(f"{API}/econtracts/{cid}/sign", json=sign_body, timeout=30)
        assert r.status_code == 200, r.text
        # Background email attempt can be slow (Emergent email API)
        rows3 = []
        for _ in range(12):
            time.sleep(2)
            rows3 = list(db.message_log.find({"contract_id": cid, "kind": "econtract_recipient_signed"}))
            if rows3:
                break
        emails3 = [x for x in rows3 if x["channel"] == "EMAIL"]
        assert emails3, f"no EMAIL row for recipient-signed: {rows3}"
        # Row must exist regardless of SENT/FAILED status (issuer is real ryuichi email, we accept either)
        assert emails3[0]["status"] in ("SENT", "FAILED"), emails3[0]

        # 8) admin signs to finish (ACTIVE)
        r = admin_session.post(f"{API}/econtracts/{cid}/sign", json=sign_body, timeout=30)
        assert r.status_code == 200, r.text
        det_final = admin_session.get(f"{API}/econtracts/{cid}", timeout=20).json()
        assert det_final["status"] == "ACTIVE", det_final["status"]


# ---------------- Regression: order enforcement ---------------- #
class TestOrderEnforcement:
    def test_send_agreement_before_confirm_returns_409(self, admin_session):
        me = admin_session.get(f"{API}/auth/me", timeout=15).json()
        # Get any consulting client belonging to admin's tenant
        cl = db.clients.find_one({"tenant_id": me["tenant_id"]})
        assert cl, "no client seed for admin tenant"
        payload = {
            "contract_type": "CONSULTING",
            "client_id": cl["id"],
            "lang": "ja",
            "terms": {
                "service_name": "TEST_OrderCheck",
                "description": "regression",
                "fee_type": "MONTHLY", "fee": 10000, "tax_mode": "exclusive", "tax_rate": 10,
                "start_date": "2026-02-01", "billing_day": 1, "payment_terms_days": 30, "auto_renew": True,
            },
            "fields": {},
        }
        r = admin_session.post(f"{API}/econtracts", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        # send-agreement before send-important → 409
        r = admin_session.post(f"{API}/econtracts/{cid}/send-agreement", timeout=15)
        assert r.status_code == 409, r.text
        # After send-important, still 409 (needs confirm)
        r = admin_session.post(f"{API}/econtracts/{cid}/send-important", timeout=15)
        assert r.status_code == 200
        r = admin_session.post(f"{API}/econtracts/{cid}/send-agreement", timeout=15)
        assert r.status_code == 409, r.text
