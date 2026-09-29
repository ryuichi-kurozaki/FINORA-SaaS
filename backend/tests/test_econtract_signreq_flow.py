"""Tests for the streamlined Consultant→Client e-contract signature-request flow.

New behavior under test:
 - POST /api/econtracts/{cid}/send-important (DRAFT->IMPORTANT_INFO_SENT) — used by '署名を依頼' button
 - POST /api/econtracts/{cid}/remind (no state change) with {ok, kind}
 - client confirm() for CONSULTING now auto-issues agreement -> CONTRACT_SENT (single step)
 - Full happy path: DRAFT -> IMPORTANT_INFO_SENT -> CONTRACT_SENT (auto) -> FIRST_PARTY_SIGNED -> ACTIVE
 - Regression: FINORA_SAAS confirm also auto-issues agreement (already tested in test_econtracts_flow.py TestAFlow).
"""
import os
import pytest
import requests

def _read_env():
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    return ""

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_env()).rstrip("/")
PWD = "Finora2026!"
ADMIN = "ryuichi.kurozaki@gmail.com"
CONSULTANT = "consultant@finora.co.jp"
CLIENT_A = "client@finora.co.jp"  # linked to 佐藤 健一

_1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
SIG_PNG = "data:image/png;base64," + _1x1 * 5


def login(email, password=PWD):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def consultant():
    return login(CONSULTANT)


@pytest.fixture(scope="module")
def admin():
    return login(ADMIN)


@pytest.fixture(scope="module")
def client_a():
    return login(CLIENT_A)


@pytest.fixture(scope="module")
def sato_client_id(consultant):
    """Client_id for '佐藤 健一' (linked to client@finora.co.jp)."""
    r = consultant.get(f"{BASE_URL}/api/data/clients", timeout=15)
    assert r.status_code == 200, r.text
    for c in r.json():
        if "佐藤" in (c.get("name") or "") or "Sato" in (c.get("name") or ""):
            return c["id"]
    pytest.skip("佐藤 健一 client not found for consultant")


class TestSignReqAndRemind:
    contract_id = None

    def test_01_consultant_creates_draft(self, consultant, sato_client_id):
        payload = {
            "contract_type": "CONSULTING",
            "client_id": sato_client_id,
            "lang": "ja",
            "terms": {"service_name": "TEST 署名依頼フロー", "fee": 30000, "start_date": "2026-02-01"},
        }
        r = consultant.post(f"{BASE_URL}/api/econtracts", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "DRAFT" and d["contract_type"] == "CONSULTING"
        TestSignReqAndRemind.contract_id = d["id"]

    def test_02_request_signature_from_draft(self, consultant):
        """署名を依頼 button → POST /send-important (DRAFT->IMPORTANT_INFO_SENT)."""
        cid = TestSignReqAndRemind.contract_id
        r = consultant.post(f"{BASE_URL}/api/econtracts/{cid}/send-important", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "IMPORTANT_INFO_SENT"
        # GET verifies persistence
        got = consultant.get(f"{BASE_URL}/api/econtracts/{cid}", timeout=10).json()
        assert got["status"] == "IMPORTANT_INFO_SENT"
        assert got.get("docs", {}).get("important"), "important doc should have been issued"

    def test_03_remind_from_important_info_sent(self, consultant):
        """リマインド button on IMPORTANT_INFO_SENT: returns {ok, kind} without changing status."""
        cid = TestSignReqAndRemind.contract_id
        r = consultant.post(f"{BASE_URL}/api/econtracts/{cid}/remind", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("kind") == "econtract_important_sent"
        # status unchanged
        got = consultant.get(f"{BASE_URL}/api/econtracts/{cid}", timeout=10).json()
        assert got["status"] == "IMPORTANT_INFO_SENT"

    def test_04_remind_from_draft_is_409(self, consultant, sato_client_id):
        """Remind at DRAFT stage must be rejected (nothing to remind)."""
        r = consultant.post(f"{BASE_URL}/api/econtracts",
                            json={"contract_type": "CONSULTING", "client_id": sato_client_id,
                                  "lang": "ja", "terms": {"service_name": "TEST remind-draft", "fee": 1000, "start_date": "2026-02-01"}}, timeout=20)
        assert r.status_code == 200, r.text
        draft_id = r.json()["id"]
        r2 = consultant.post(f"{BASE_URL}/api/econtracts/{draft_id}/remind", timeout=10)
        assert r2.status_code == 409, r2.text
        # cleanup: cancel
        consultant.post(f"{BASE_URL}/api/econtracts/{draft_id}/cancel", json={"reason": "cleanup"}, timeout=10)

    def test_05_client_confirm_auto_issues_agreement(self, client_a):
        """Client confirms → contract auto-advances to CONTRACT_SENT (agreement auto-issued)."""
        cid = TestSignReqAndRemind.contract_id
        r = client_a.post(f"{BASE_URL}/api/econtracts/{cid}/confirm", timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "CONTRACT_SENT", \
            f"expected auto-advance to CONTRACT_SENT, got {r.json()}"
        # Verify agreement doc issued & client sees the sign card availability (can_receive & status)
        got = client_a.get(f"{BASE_URL}/api/econtracts/{cid}", timeout=10).json()
        assert got["status"] == "CONTRACT_SENT"
        assert got["can_receive"] is True
        assert got.get("docs", {}).get("agreement"), "agreement doc must be auto-issued on confirm"

    def test_06_remind_from_contract_sent(self, consultant):
        """リマインド from CONTRACT_SENT: returns kind=econtract_agreement_sent; status unchanged."""
        cid = TestSignReqAndRemind.contract_id
        r = consultant.post(f"{BASE_URL}/api/econtracts/{cid}/remind", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("kind") == "econtract_agreement_sent"
        got = consultant.get(f"{BASE_URL}/api/econtracts/{cid}", timeout=10).json()
        assert got["status"] == "CONTRACT_SENT"

    def test_07_client_signs(self, client_a):
        cid = TestSignReqAndRemind.contract_id
        r = client_a.post(f"{BASE_URL}/api/econtracts/{cid}/sign",
                          json={"name": "佐藤 健一", "signature_png": SIG_PNG, "agree": True}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "FIRST_PARTY_SIGNED"

    def test_08_consultant_signs_active(self, consultant):
        cid = TestSignReqAndRemind.contract_id
        r = consultant.post(f"{BASE_URL}/api/econtracts/{cid}/sign",
                            json={"name": "Consultant", "signature_png": SIG_PNG, "agree": True}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ACTIVE"

    def test_09_remind_at_active_is_409(self, consultant):
        cid = TestSignReqAndRemind.contract_id
        r = consultant.post(f"{BASE_URL}/api/econtracts/{cid}/remind", timeout=10)
        assert r.status_code == 409, r.text

    def test_10_client_role_cannot_remind(self, client_a, consultant, sato_client_id):
        """Client role must not be allowed to POST /remind (is_issuer only)."""
        # Create fresh draft + send-important to reach IMPORTANT_INFO_SENT
        r = consultant.post(f"{BASE_URL}/api/econtracts",
                            json={"contract_type": "CONSULTING", "client_id": sato_client_id,
                                  "lang": "ja", "terms": {"service_name": "TEST client-remind-forbid", "fee": 1000, "start_date": "2026-02-01"}}, timeout=15)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        assert consultant.post(f"{BASE_URL}/api/econtracts/{cid}/send-important", timeout=15).status_code == 200
        r2 = client_a.post(f"{BASE_URL}/api/econtracts/{cid}/remind", timeout=10)
        assert r2.status_code == 403, r2.text
        consultant.post(f"{BASE_URL}/api/econtracts/{cid}/cancel", json={"reason": "cleanup"}, timeout=10)
