"""Per-consultant payouts + clients.whatsapp + accounts.account_number-removed tests.

Covers all iteration_15 features:
  * accounts: account_number ignored on POST/PUT; startup migration unset it in Mongo
  * clients: new 'whatsapp' field stored encrypted, returned decrypted
  * GET/PUT /api/payouts/bank on users.payout_bank (admin AND consultant), client 403, demo forbid
  * /api/auth/me returns payout_bank_registered bool, hides payout_bank
  * Card-pay gating per client via consultant bank (GET /invoices card_enabled + POST /stripe/checkout/invoice 409)
  * Platform ledger grouped per-consultant (GET /api/platform/payouts {payees, history})
  * POST /api/platform/payouts/{user_id} marks sent (409 no bank / amount<=0), consultant GET /api/payouts history
  * sign_notify._deliver whatsapp fallback to clients.whatsapp when user has no whatsapp_phone
"""
import json
import os
import re
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

sys.path.insert(0, "/app/backend")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PLATFORM_ADMIN = ("ryuichi.kurozaki@gmail.com", "Finora2026!")
CONSULTANT = ("consultant@finora.co.jp", "Finora2026!")
CLIENT = ("client@finora.co.jp", "Finora2026!")
CONSULTANT_B = ("consultantb@finora.co.jp", "Finora2026!")

TEST_BANK = {
    "bank_name": "三菱UFJ銀行",
    "bank_code": "0005",
    "branch_name": "東京営業部",
    "branch_code": "001",
    "account_type": "ORDINARY",
    "account_number": "1234567",
    "holder_kana": "カ）フィノラ",
}
CONSULTANT_BANK = {**TEST_BANK, "account_number": "7654321", "holder_kana": "カ）コンサルタント"}
TAG = f"TEST_PAYOUT_{uuid.uuid4().hex[:8]}"


def login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def admin_s():
    return login(*PLATFORM_ADMIN)


@pytest.fixture(scope="session")
def consultant_s():
    return login(*CONSULTANT)


@pytest.fixture(scope="session")
def client_s():
    return login(*CLIENT)


@pytest.fixture(scope="session")
def admin_b_s():
    return login(*CONSULTANT_B)


@pytest.fixture(scope="session")
def admin_id(admin_s):
    return admin_s.get(f"{BASE}/api/auth/me").json()["id"]


@pytest.fixture(scope="session")
def consultant_id(consultant_s):
    return consultant_s.get(f"{BASE}/api/auth/me").json()["id"]


@pytest.fixture(scope="session")
def admin_b_id(admin_b_s):
    return admin_b_s.get(f"{BASE}/api/auth/me").json()["id"]


@pytest.fixture(scope="session")
def tenant_a_id(admin_s):
    return admin_s.get(f"{BASE}/api/auth/me").json()["tenant_id"]


# --- session-scoped: register admin & consultant banks so downstream flows can run ---
@pytest.fixture(scope="session", autouse=True)
def ensure_admin_bank(admin_s):
    admin_s.put(f"{BASE}/api/payouts/bank", json=TEST_BANK)


@pytest.fixture(scope="session")
def ensure_consultant_bank(consultant_s):
    r = consultant_s.put(f"{BASE}/api/payouts/bank", json=CONSULTANT_BANK)
    assert r.status_code == 200, r.text


# ============================================================
# 1. auth/me
# ============================================================
class TestAuthMe:
    def test_auth_me_hides_payout_bank_shows_flag_admin(self, admin_s):
        me = admin_s.get(f"{BASE}/api/auth/me").json()
        assert "payout_bank" not in me
        assert me["payout_bank_registered"] is True

    def test_auth_me_flag_false_without_bank(self, admin_b_s):
        me = admin_b_s.get(f"{BASE}/api/auth/me").json()
        assert me["payout_bank_registered"] is False


# ============================================================
# 2. Bank RBAC & validation (per-user)
# ============================================================
class TestBankRBAC:
    def test_consultant_can_get(self, consultant_s):
        r = consultant_s.get(f"{BASE}/api/payouts/bank")
        assert r.status_code == 200

    def test_consultant_can_put(self, consultant_s, ensure_consultant_bank):
        r = consultant_s.get(f"{BASE}/api/payouts/bank")
        assert r.json()["bank"]["account_number"] == "7654321"

    def test_client_forbidden_get(self, client_s):
        r = client_s.get(f"{BASE}/api/payouts/bank")
        assert r.status_code == 403

    def test_client_forbidden_put(self, client_s):
        r = client_s.put(f"{BASE}/api/payouts/bank", json=TEST_BANK)
        assert r.status_code == 403


class TestBankValidation:
    def test_bad_acct_6(self, admin_s):
        assert admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "account_number": "123456"}).status_code == 422

    def test_bad_acct_8(self, admin_s):
        assert admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "account_number": "12345678"}).status_code == 422

    def test_bad_holder(self, admin_s):
        assert admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "holder_kana": "abc"}).status_code == 422

    def test_bad_type(self, admin_s):
        assert admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "account_type": "XXX"}).status_code == 422


# ============================================================
# 3. Encryption/persistence (users.payout_bank)
# ============================================================
class TestBankPersistence:
    def test_roundtrip(self, admin_s):
        assert admin_s.put(f"{BASE}/api/payouts/bank", json=TEST_BANK).status_code == 200
        g = admin_s.get(f"{BASE}/api/payouts/bank").json()
        assert g["bank"]["account_number"] == "1234567"
        assert g["updated_at"]

    @pytest.mark.asyncio
    async def test_encrypted_in_users_collection(self, admin_id):
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        doc = await cli[os.environ["DB_NAME"]].users.find_one({"id": admin_id})
        pb = doc.get("payout_bank")
        assert pb and pb.get("enc")
        assert "1234567" not in json.dumps(pb, ensure_ascii=False)
        cli.close()

    @pytest.mark.asyncio
    async def test_no_tenant_payout_bank(self, tenant_a_id):
        """Old tenant-level payout_bank removed by startup migration."""
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        t = await cli[os.environ["DB_NAME"]].tenants.find_one({"id": tenant_a_id})
        assert "payout_bank" not in t
        cli.close()


# ============================================================
# 4. accounts.account_number removal
# ============================================================
class TestAccountsAccountNumber:
    def test_create_account_without_account_number(self, client_s):
        # accounts are client-owned; must be created by the client user
        me = client_s.get(f"{BASE}/api/auth/me").json()
        body = {"client_id": me["client_id"], "institution": f"{TAG}_bank", "account_type": "bank",
                "region": "domestic", "currency": "JPY", "account_number": "SHOULD_BE_IGNORED_1234"}
        r = client_s.post(f"{BASE}/api/data/accounts", json=body)
        assert r.status_code == 200, r.text
        acct = r.json()
        assert "account_number" not in acct
        aid = acct["id"]
        g = client_s.get(f"{BASE}/api/data/accounts/{aid}").json()
        assert "account_number" not in g
        upd = client_s.put(f"{BASE}/api/data/accounts/{aid}",
                           json={**body, "account_number": "XXX", "branch": "西"}).json()
        assert "account_number" not in upd
        client_s.delete(f"{BASE}/api/data/accounts/{aid}")

    @pytest.mark.asyncio
    async def test_existing_accounts_migrated(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        n = await cli[os.environ["DB_NAME"]].accounts.count_documents({"account_number": {"$exists": True}})
        assert n == 0
        cli.close()


# ============================================================
# 5. clients.whatsapp field (encrypted)
# ============================================================
class TestClientsWhatsapp:
    @pytest.fixture
    def temp_client(self, admin_s):
        body = {"client_type": "individual", "name": f"{TAG}_WhatsCli", "email": f"{TAG}@example.com",
                "whatsapp": "+81 90-1234-5678", "phone": "03-1234-5678"}
        r = admin_s.post(f"{BASE}/api/data/clients", json=body)
        assert r.status_code == 200, r.text
        c = r.json()
        yield c
        admin_s.delete(f"{BASE}/api/data/clients/{c['id']}")

    def test_whatsapp_saved_and_returned_decrypted(self, admin_s, temp_client):
        # POST response returns decrypted
        assert temp_client.get("whatsapp") == "+81 90-1234-5678"
        # GET returns decrypted
        got = admin_s.get(f"{BASE}/api/data/clients/{temp_client['id']}").json()
        assert got["whatsapp"] == "+81 90-1234-5678"

    @pytest.mark.asyncio
    async def test_whatsapp_stored_encrypted(self, temp_client):
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        doc = await cli[os.environ["DB_NAME"]].clients.find_one({"id": temp_client["id"]})
        assert doc["whatsapp"] != "+81 90-1234-5678"
        # Should be a non-empty string cipher
        assert isinstance(doc["whatsapp"], str) and len(doc["whatsapp"]) > 10
        cli.close()


# ============================================================
# 6. Card-pay gating (per-consultant bank)
# ============================================================
class TestCardGating:
    def test_invoices_card_enabled_true_for_clients_whose_consultant_banked(self, admin_s, ensure_consultant_bank):
        """Both admin and consultant have banks; all clients in tenant A get card_enabled=True."""
        invs = admin_s.get(f"{BASE}/api/invoices").json()
        assert invs
        # Not all clients might be assigned to a banked consultant -> allow mixed; at least some True
        assert any(i.get("card_enabled") for i in invs)

    def test_invoices_card_enabled_false_tenant_b(self, admin_b_s):
        invs = admin_b_s.get(f"{BASE}/api/invoices").json()
        for i in invs:
            assert i.get("card_enabled") is False


class TestCheckoutGating:
    @pytest.fixture(scope="class")
    def payable_inv(self, client_s):
        invs = client_s.get(f"{BASE}/api/invoices").json()
        payable = [i for i in invs if i["status"] in ("ISSUED", "PARTIALLY_PAID", "OVERDUE") and i["balance"] > 0]
        if not payable:
            pytest.skip("no payable invoice")
        return payable[0]

    def test_checkout_passes_gating(self, client_s, payable_inv):
        # Client 佐藤 健一's consultant should have a bank at this point
        r = client_s.post(f"{BASE}/api/stripe/checkout/invoice",
                          json={"origin_url": "https://finora.co.jp", "invoice_id": payable_inv["id"]})
        # 200 or Stripe 400 both mean gating passed
        assert r.status_code in (200, 400), r.text
        if r.status_code == 400:
            assert "Stripe" in r.text

    @pytest.mark.asyncio
    async def test_checkout_409_when_consultant_bank_missing(self, client_s, payable_inv):
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        # Find the client's consultant, temporarily unset their bank
        client_doc = await db.clients.find_one({"id": payable_inv["client_id"]}, {"consultant_id": 1})
        cid = client_doc["consultant_id"]
        # Also unset admin bank IF admin is that consultant
        u = await db.users.find_one({"id": cid}, {"payout_bank": 1})
        prev = u.get("payout_bank") if u else None
        try:
            await db.users.update_one({"id": cid}, {"$unset": {"payout_bank": ""}})
            r = client_s.post(f"{BASE}/api/stripe/checkout/invoice",
                              json={"origin_url": "https://finora.co.jp", "invoice_id": payable_inv["id"]})
            assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"
        finally:
            if prev:
                await db.users.update_one({"id": cid}, {"$set": {"payout_bank": prev}})
            cli.close()


# ============================================================
# 7. Platform ledger grouped per consultant
# ============================================================
class TestPlatformPayouts:
    @pytest.fixture(scope="class")
    def seeded(self, tenant_a_id):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]

        async def _setup():
            # Use a client belonging to consultant@finora.co.jp so the payee is the consultant user
            consultant_user = await db.users.find_one({"email": "consultant@finora.co.jp"}, {"id": 1})
            client_doc = await db.clients.find_one({"tenant_id": tenant_a_id, "consultant_id": consultant_user["id"]})
            assert client_doc, "expected a client assigned to consultant@finora.co.jp"
            inv = await db.invoices.find_one({"tenant_id": tenant_a_id, "client_id": client_doc["id"]})
            if not inv:
                # fallback: any invoice
                inv = await db.invoices.find_one({"tenant_id": tenant_a_id})
                client_doc = await db.clients.find_one({"id": inv["client_id"]})
            cons_id = client_doc["consultant_id"]
            p1 = {"id": f"{TAG}_p1", "tenant_id": tenant_a_id, "client_id": client_doc["id"],
                  "invoice_id": inv["id"], "invoice_number": inv["number"], "date": "2026-01-05",
                  "amount": 100000, "method": "CREDIT_CARD", "source": "STRIPE",
                  "stripe_fee": 3600, "stripe_fee_estimated": False, "payee_id": cons_id,
                  "created_at": "2026-01-05T00:00:00", "reference": f"pi_{TAG}_1"}
            p2 = {"id": f"{TAG}_p2", "tenant_id": tenant_a_id, "client_id": client_doc["id"],
                  "invoice_id": inv["id"], "invoice_number": inv["number"], "date": "2026-01-10",
                  "amount": 50000, "method": "CREDIT_CARD", "source": "STRIPE",
                  "created_at": "2026-01-10T00:00:00", "reference": f"pi_{TAG}_2"}
            await db.payments.insert_many([p1, p2])
            return {"consultant_id": cons_id}

        info = __import__("asyncio").get_event_loop().run_until_complete(_setup())
        yield info

        async def _cleanup():
            await db.payments.delete_many({"id": {"$regex": f"^{TAG}"}})
            await db.payouts.delete_many({"note": {"$regex": TAG}})
            await db.notifications.delete_many({"kind": "payout_sent", "data.label": {"$regex": TAG}})
            cli.close()

        __import__("asyncio").get_event_loop().run_until_complete(_cleanup())

    def test_platform_payouts_returns_payees_key(self, admin_s, seeded):
        r = admin_s.get(f"{BASE}/api/platform/payouts")
        assert r.status_code == 200
        j = r.json()
        assert "payees" in j and "history" in j
        # our consultant should appear
        by_id = {p["payee_id"]: p for p in j["payees"]}
        cid = seeded["consultant_id"]
        assert cid in by_id
        row = by_id[cid]
        assert "bank" in row and row["bank"] and row["bank"]["account_number"] == "7654321"
        assert row["payee_email"] == "consultant@finora.co.jp"
        assert row["tenant_name"]
        # our items
        our = {i["payment_id"]: i for i in row["items"] if i["payment_id"].startswith(TAG)}
        assert set(our.keys()) == {f"{TAG}_p1", f"{TAG}_p2"}
        assert our[f"{TAG}_p1"]["stripe_fee"] == 3600
        assert our[f"{TAG}_p1"]["pending"] == 96400
        assert our[f"{TAG}_p2"]["fee_estimated"] is True
        assert our[f"{TAG}_p2"]["pending"] == 48200

    def test_consultant_403_platform_payouts(self, consultant_s):
        assert consultant_s.get(f"{BASE}/api/platform/payouts").status_code == 403

    def test_mark_sent_409_without_bank(self, admin_s, admin_b_id):
        r = admin_s.post(f"{BASE}/api/platform/payouts/{admin_b_id}",
                         json={"transfer_fee": 0, "transfer_date": "2026-01-20", "note": TAG})
        assert r.status_code == 409

    def test_mark_sent_creates_and_consultant_sees_history(self, admin_s, consultant_s, seeded):
        cid = seeded["consultant_id"]
        r = admin_s.post(f"{BASE}/api/platform/payouts/{cid}",
                         json={"transfer_fee": 330, "transfer_date": "2026-01-20", "note": TAG})
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["status"] == "SENT"
        assert doc["bank"]["account_number"].startswith("***")
        assert doc["payee_id"] == cid

        # After settle, our items filtered out
        post = admin_s.get(f"{BASE}/api/platform/payouts").json()
        row = next((p for p in post["payees"] if p["payee_id"] == cid), None)
        our = [] if row is None else [i for i in row["items"] if i["payment_id"].startswith(TAG)]
        assert our == []

        # consultant's GET /api/payouts shows history
        hist = consultant_s.get(f"{BASE}/api/payouts").json()
        assert doc["id"] in [h["id"] for h in hist["history"]]


# ============================================================
# 8. sign_notify._deliver whatsapp fallback to clients.whatsapp
# ============================================================
class TestSignNotifyFallback:
    @pytest.mark.asyncio
    async def test_deliver_falls_back_to_client_whatsapp(self, tenant_a_id):
        """Set clients.whatsapp on a temporary client + user, clear user.whatsapp_phone, invoke _deliver, expect WHATSAPP message_log with the fallback digits."""
        import asyncio  # noqa: F401
        from motor.motor_asyncio import AsyncIOMotorClient
        from core import encrypt
        import sign_notify
        from sign_notify import _deliver, TXT
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]

        # Find client user & its client (client@finora.co.jp -> 佐藤 健一)
        cuser = await db.users.find_one({"email": "client@finora.co.jp"})
        assert cuser and cuser.get("client_id")
        client_doc = await db.clients.find_one({"id": cuser["client_id"]})

        # Save & override state
        prev_user_wa = cuser.get("whatsapp_phone")
        prev_user_opt = cuser.get("whatsapp_opt_in")
        prev_client_wa = client_doc.get("whatsapp")
        fake_number = "+81 80-9999-8888"
        prev_wa_url = sign_notify.WA_URL
        sign_notify.WA_URL = "http://127.0.0.1:1/whatsapp"  # unreachable -> FAILED log
        try:
            await db.users.update_one({"id": cuser["id"]}, {"$unset": {"whatsapp_phone": "", "whatsapp_opt_in": ""}})
            await db.clients.update_one({"id": client_doc["id"]}, {"$set": {"whatsapp": encrypt(fake_number)}})

            # Fabricate a minimal contract dict as sign_notify expects
            c = {"id": f"{TAG}_contract", "tenant_id": tenant_a_id, "number": f"{TAG}-CT-1",
                 "lang": "ja", "terms": {"service_name": "テストサービス"}}
            fresh_user = await db.users.find_one({"id": cuser["id"]})
            x = TXT["ja"]
            await _deliver(c, fresh_user, "econtract_agreement_sent", x,
                           "テスト件名", "テスト本文", x["cta"])

            # Expect a WHATSAPP entry (SENT or FAILED — preview may not reach the service)
            wa_log = await db.message_log.find_one({"contract_id": c["id"], "channel": "WHATSAPP"})
            assert wa_log is not None, "expected a WHATSAPP message_log entry from fallback"
            digits_only = re.sub(r"\D", "", fake_number)
            assert wa_log["to"] == digits_only, f"expected fallback phone {digits_only}, got {wa_log['to']}"
            # cleanup log
            await db.message_log.delete_many({"contract_id": c["id"]})
        finally:
            sign_notify.WA_URL = prev_wa_url
            # restore user
            rest = {}
            if prev_user_wa is not None:
                rest["whatsapp_phone"] = prev_user_wa
            if prev_user_opt is not None:
                rest["whatsapp_opt_in"] = prev_user_opt
            if rest:
                await db.users.update_one({"id": cuser["id"]}, {"$set": rest})
            if prev_client_wa is None:
                await db.clients.update_one({"id": client_doc["id"]}, {"$unset": {"whatsapp": ""}})
            else:
                await db.clients.update_one({"id": client_doc["id"]}, {"$set": {"whatsapp": prev_client_wa}})
            cli.close()
