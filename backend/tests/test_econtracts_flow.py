"""End-to-end pytest for FINORA two-tier e-contract flow (B flow, isolation, amendment, A flow)."""
import os
import time
import base64
import pytest
import requests

def _read_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_env()).rstrip("/")
PWD = "Finora2026!"

ADMIN = "ryuichi.kurozaki@gmail.com"
CONSULTANT = "consultant@finora.co.jp"
CLIENT_A = "client@finora.co.jp"          # 佐藤 健一
CLIENT_B = "client2@finora.co.jp"         # Ana Paula Ferreira
CONSULTANT_B = "consultantb@finora.co.jp"

# 1x1 transparent PNG (base64) — enough >100 chars once with data URL
_1x1 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
SIG_PNG = "data:image/png;base64," + _1x1 * 5  # ensure >100 chars


def login(email, password=PWD):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return login(ADMIN)


@pytest.fixture(scope="module")
def client_b():
    return login(CLIENT_B)


@pytest.fixture(scope="module")
def client_a():
    return login(CLIENT_A)


@pytest.fixture(scope="module")
def consultant_b():
    return login(CONSULTANT_B)


@pytest.fixture(scope="module")
def client2_client_id(admin):
    # Find the client_id linked to client2@finora.co.jp (Ana Paula Ferreira)
    r = admin.get(f"{BASE_URL}/api/data/clients", timeout=15)
    assert r.status_code == 200
    clients = r.json()
    match = [c for c in clients if "Ana Paula" in (c.get("name") or "") or "Ferreira" in (c.get("name") or "")]
    assert match, f"Ana Paula Ferreira client not found. Got: {[c.get('name') for c in clients]}"
    return match[0]["id"]


# ---------------- B FLOW (CONSULTING) ----------------
class TestBFlow:
    contract_id = None

    def test_01_create_draft(self, admin, client2_client_id):
        payload = {
            "contract_type": "CONSULTING",
            "client_id": client2_client_id,
            "lang": "pt",
            "terms": {"service_name": "Consultoria Financeira TEST", "fee": 20000, "start_date": "2026-01-15"},
        }
        r = admin.post(f"{BASE_URL}/api/econtracts", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "DRAFT"
        assert data["contract_type"] == "CONSULTING"
        assert data["lang"] == "pt"
        TestBFlow.contract_id = data["id"]

    def test_02_client_cannot_get_draft(self, client_b):
        r = client_b.get(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}", timeout=10)
        assert r.status_code == 404

    def test_03_send_agreement_before_confirm_409(self, admin):
        r = admin.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/send-agreement", timeout=10)
        assert r.status_code == 409, r.text

    def test_04_send_important(self, admin):
        r = admin.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/send-important", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "IMPORTANT_INFO_SENT"

    def test_05_staff_cannot_confirm(self, admin):
        # admin is issuer, not recipient in B flow → should be 403
        r = admin.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/confirm", timeout=10)
        assert r.status_code == 403, r.text

    def test_06_client_confirm(self, client_b):
        r = client_b.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/confirm", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "IMPORTANT_INFO_CONFIRMED"

    def test_07_issuer_sign_before_recipient_409(self, admin):
        r = admin.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/sign",
                       json={"name": "Ryuichi", "signature_png": SIG_PNG, "agree": True}, timeout=15)
        # Should be 409 because status is IMPORTANT_INFO_CONFIRMED (agreement not yet sent for CONSULTING)
        assert r.status_code == 409, r.text

    def test_08_send_agreement(self, admin):
        r = admin.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/send-agreement", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "CONTRACT_SENT"

    def test_09_client_sign(self, client_b):
        r = client_b.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/sign",
                          json={"name": "Ana Paula Ferreira", "signature_png": SIG_PNG, "agree": True}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "FIRST_PARTY_SIGNED"

    def test_10_issuer_sign_active(self, admin):
        r = admin.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/sign",
                       json={"name": "Ryuichi Kurozaki", "signature_png": SIG_PNG, "agree": True}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ACTIVE"

    def test_11_detail_documents_acts_pdf(self, admin, client2_client_id):
        r = admin.get(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        docs = d["documents"]
        assert len(docs) == 2, f"Expected 2 docs, got {len(docs)}"
        for doc in docs:
            assert doc["integrity_ok"] is True
            assert doc.get("pdf_file_id"), f"pdf_file_id missing for {doc['document_type']}"
        acts = d["acts"]
        kinds = {(a["act"], a["party"]) for a in acts}
        assert ("CONFIRM", "RECIPIENT") in kinds
        assert ("SIGN", "RECIPIENT") in kinds
        assert ("SIGN", "ISSUER") in kinds
        # ip & user_agent present
        for a in acts:
            if a["act"] in ("CONFIRM", "SIGN"):
                assert "ip" in a and "user_agent" in a
        assert len(d["history"]) > 0

        # PDF download
        agreement_doc = [x for x in docs if x["document_type"] == "CONSULTING_AGREEMENT"][0]
        r2 = admin.get(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/docs/{agreement_doc['id']}/pdf", timeout=30)
        assert r2.status_code == 200
        assert r2.content[:4] == b"%PDF", f"Not a PDF: {r2.content[:20]}"

        # DRAFT invoice for the client
        r3 = admin.get(f"{BASE_URL}/api/invoices?client_id={client2_client_id}", timeout=10)
        assert r3.status_code == 200
        invs = r3.json()
        drafts = [i for i in invs if i.get("status") == "DRAFT" and i.get("client_id") == client2_client_id]
        assert drafts, "No DRAFT invoice created"

        # Billing contract ACTIVE
        r4 = admin.get(f"{BASE_URL}/api/data/contracts?client_id={client2_client_id}", timeout=10)
        assert r4.status_code == 200
        bcs = [c for c in r4.json() if c.get("status") == "ACTIVE" and c.get("econtract_id") == TestBFlow.contract_id]
        assert bcs, "No ACTIVE billing contract linked"

        # Client sees contract document
        r5 = admin.get(f"{BASE_URL}/api/documents?client_id={client2_client_id}", timeout=10)
        assert r5.status_code == 200
        contract_docs = [x for x in r5.json() if x.get("category") == "contract"]
        assert contract_docs, "No contract category document"


# ---------------- ISOLATION ----------------
class TestIsolation:
    def test_client_a_cannot_get_client_b_contract(self, client_a):
        assert TestBFlow.contract_id
        r = client_a.get(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}", timeout=10)
        assert r.status_code == 404

    def test_consultant_b_other_tenant_cannot_get(self, consultant_b):
        r = consultant_b.get(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}", timeout=10)
        assert r.status_code == 404

    def test_consultant_scoped_list(self):
        s = login(CONSULTANT)
        r = s.get(f"{BASE_URL}/api/econtracts?type=CONSULTING", timeout=10)
        assert r.status_code == 200
        contracts = r.json()
        # consultant assigned to Ana Paula → should see this one
        assert any(c["id"] == TestBFlow.contract_id for c in contracts), "consultant should see own client's contract"

    def test_legacy_write_blocked(self, admin, client2_client_id):
        r = admin.post(f"{BASE_URL}/api/data/contracts",
                       json={"client_id": client2_client_id, "name": "legacy", "service_name": "x", "fee": 1000, "start_date": "2026-01-01"}, timeout=10)
        assert r.status_code == 403, f"legacy write should be 403, got {r.status_code} {r.text[:200]}"


# ---------------- AMENDMENT ----------------
class TestAmendment:
    v2_id = None

    def test_amend_creates_v2_draft(self, admin):
        r = admin.post(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}/amend", timeout=15)
        assert r.status_code == 200, r.text
        new = r.json()
        assert new["status"] == "DRAFT"
        assert new["version"] == 2
        # same contract number
        r0 = admin.get(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}", timeout=10)
        assert new["number"] == r0.json()["number"]
        TestAmendment.v2_id = new["id"]

    def test_v2_full_flow_and_v1_ended(self, admin, client_b, client2_client_id):
        cid = TestAmendment.v2_id
        assert admin.post(f"{BASE_URL}/api/econtracts/{cid}/send-important", timeout=15).status_code == 200
        assert client_b.post(f"{BASE_URL}/api/econtracts/{cid}/confirm", timeout=15).status_code == 200
        assert admin.post(f"{BASE_URL}/api/econtracts/{cid}/send-agreement", timeout=15).status_code == 200
        assert client_b.post(f"{BASE_URL}/api/econtracts/{cid}/sign",
                             json={"name": "Ana", "signature_png": SIG_PNG, "agree": True}, timeout=15).status_code == 200
        r = admin.post(f"{BASE_URL}/api/econtracts/{cid}/sign",
                       json={"name": "Ryuichi", "signature_png": SIG_PNG, "agree": True}, timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ACTIVE"
        # v1 ended AMENDED
        v1 = admin.get(f"{BASE_URL}/api/econtracts/{TestBFlow.contract_id}", timeout=10).json()
        assert v1["status"] == "ENDED"
        assert v1.get("end_reason") == "AMENDED"

    def test_end_v2(self, admin):
        cid = TestAmendment.v2_id
        r = admin.post(f"{BASE_URL}/api/econtracts/{cid}/end",
                       json={"end_date": "2026-06-30", "reason": "TEST end", "consultant_login": "read_only",
                             "client_access": "read_only", "retention_days": 30}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ENDED"
        v2 = admin.get(f"{BASE_URL}/api/econtracts/{cid}", timeout=10).json()
        # Billing contract must be ENDED
        bcid = v2.get("billing_contract_id")
        if bcid:
            bc_list = admin.get(f"{BASE_URL}/api/data/contracts", timeout=10).json()
            bc = [b for b in bc_list if b["id"] == bcid]
            assert bc and bc[0]["status"] == "ENDED"


# ---------------- A FLOW (FINORA_SAAS) ----------------
class TestAFlow:
    signup_email = None
    signup_session = None
    contract_id = None

    def test_01_signup_new_consultant(self):
        ts = int(time.time())
        TestAFlow.signup_email = f"test_signup_{ts}@example.com"
        body = {
            "name": "Test Signup", "company_name": "Signup TEST LLC", "entity_type": "corporation",
            "email": TestAFlow.signup_email, "phone": "0312345678", "address": "Tokyo",
            "profile": "test", "qualifications": "", "plan_code": "TRIAL",
            "password": "TestSignup2026!",
        }
        r = requests.post(f"{BASE_URL}/api/public/signup", json=body, timeout=20)
        if r.status_code == 429:
            pytest.skip("Signup rate-limited (5/IP/hour)")
        assert r.status_code == 200, r.text
        TestAFlow.signup_session = login(TestAFlow.signup_email, "TestSignup2026!")

    def test_02_finora_contract_auto_sent(self):
        s = TestAFlow.signup_session
        r = s.get(f"{BASE_URL}/api/econtracts?type=FINORA_SAAS&mine=true", timeout=10)
        assert r.status_code == 200, r.text
        contracts = r.json()
        assert len(contracts) == 1
        assert contracts[0]["status"] == "IMPORTANT_INFO_SENT"
        TestAFlow.contract_id = contracts[0]["id"]

    def test_03_gated_endpoints_before_active(self):
        s = TestAFlow.signup_session
        r = s.post(f"{BASE_URL}/api/data/clients",
                   json={"name": "TEST Client", "email": "x@example.com"}, timeout=10)
        assert r.status_code == 403, f"clients POST should be 403 before A ACTIVE, got {r.status_code}"
        # invitations requires client_id → gated first
        r2 = s.post(f"{BASE_URL}/api/invitations",
                    json={"client_id": "nonexistent", "email": "inv@example.com"}, timeout=10)
        assert r2.status_code == 403

    def test_04_consultant_confirm_auto_sends_agreement(self):
        s = TestAFlow.signup_session
        r = s.post(f"{BASE_URL}/api/econtracts/{TestAFlow.contract_id}/confirm", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "CONTRACT_SENT"

    def test_05_consultant_sign(self):
        s = TestAFlow.signup_session
        r = s.post(f"{BASE_URL}/api/econtracts/{TestAFlow.contract_id}/sign",
                   json={"name": "Test Signup", "signature_png": SIG_PNG, "agree": True}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "FIRST_PARTY_SIGNED"

    def test_06_platform_admin_sees_and_signs(self, admin):
        r = admin.get(f"{BASE_URL}/api/econtracts?type=FINORA_SAAS", timeout=10)
        assert r.status_code == 200
        found = [c for c in r.json() if c["id"] == TestAFlow.contract_id]
        assert found and found[0]["status"] == "FIRST_PARTY_SIGNED"
        r2 = admin.post(f"{BASE_URL}/api/econtracts/{TestAFlow.contract_id}/sign",
                        json={"name": "Ryuichi Kurozaki", "signature_png": SIG_PNG, "agree": True}, timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "ACTIVE"

    def test_07_gate_lifted(self):
        s = TestAFlow.signup_session
        r = s.post(f"{BASE_URL}/api/data/clients",
                   json={"name": "TEST_ClientAfter", "email": f"clt{int(time.time())}@example.com"}, timeout=10)
        assert r.status_code in (200, 201), f"client create after A ACTIVE should succeed: {r.status_code} {r.text}"

    def test_08_consultantb_isolation(self, consultant_b):
        r = consultant_b.get(f"{BASE_URL}/api/econtracts/{TestAFlow.contract_id}", timeout=10)
        assert r.status_code == 404

    def test_09_end_A_with_blocked_login(self, admin):
        r = admin.post(f"{BASE_URL}/api/econtracts/{TestAFlow.contract_id}/end",
                       json={"end_date": "2026-06-30", "reason": "TEST A end",
                             "consultant_login": "blocked", "client_access": "read_only",
                             "retention_days": 0}, timeout=15)
        assert r.status_code == 200, r.text
        # Consultant login should now return 403
        r2 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"email": TestAFlow.signup_email, "password": "TestSignup2026!"}, timeout=15)
        assert r2.status_code == 403, f"blocked consultant should get 403, got {r2.status_code} {r2.text[:200]}"
