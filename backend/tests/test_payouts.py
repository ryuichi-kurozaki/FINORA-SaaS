"""Payouts (manual bank transfer) end-to-end tests.

Covers:
  * GET/PUT /api/payouts/bank (validation, role scoping, encryption)
  * Card-pay gating via GET /api/invoices card_enabled and POST /api/stripe/checkout/invoice (409 without bank)
  * Payout ledger (GET/POST /api/platform/payouts, fee estimation, refund-after-payout negative pending)
  * Regression: stripe_payments._fulfill still stores stripe_fee (record_fee falls back to estimate)
"""
import json
import os
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


def login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
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
def tenant_a_id(admin_s):
    return admin_s.get(f"{BASE}/api/auth/me").json()["tenant_id"]


@pytest.fixture(scope="session")
def tenant_b_id(admin_b_s):
    return admin_b_s.get(f"{BASE}/api/auth/me").json()["tenant_id"]


# ---------- 1. bank RBAC & validation ----------

class TestBankRBAC:
    def test_consultant_forbidden_get(self, consultant_s):
        r = consultant_s.get(f"{BASE}/api/payouts/bank")
        assert r.status_code == 403

    def test_client_forbidden_get(self, client_s):
        r = client_s.get(f"{BASE}/api/payouts/bank")
        assert r.status_code == 403

    def test_consultant_forbidden_put(self, consultant_s):
        r = consultant_s.put(f"{BASE}/api/payouts/bank", json=TEST_BANK)
        assert r.status_code == 403


class TestBankValidation:
    def test_bad_account_number_6_digits(self, admin_s):
        r = admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "account_number": "123456"})
        assert r.status_code == 422

    def test_bad_account_number_8_digits(self, admin_s):
        r = admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "account_number": "12345678"})
        assert r.status_code == 422

    def test_bad_holder_kana_ascii(self, admin_s):
        r = admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "holder_kana": "abc"})
        assert r.status_code == 422

    def test_bad_account_type(self, admin_s):
        r = admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "account_type": "XXX"})
        assert r.status_code == 422

    def test_bad_bank_code_3_digits(self, admin_s):
        r = admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "bank_code": "123"})
        assert r.status_code == 422

    def test_optional_codes_empty_ok(self, admin_s):
        # We'll actually save this later; just verify shape here by putting then restoring
        r = admin_s.put(f"{BASE}/api/payouts/bank", json={**TEST_BANK, "bank_code": "", "branch_code": ""})
        assert r.status_code == 200, r.text


# ---------- 2. Save bank + persistence + encryption ----------

class TestBankPersistence:
    def test_put_and_get_roundtrip(self, admin_s):
        r = admin_s.put(f"{BASE}/api/payouts/bank", json=TEST_BANK)
        assert r.status_code == 200
        data = r.json()["bank"]
        assert data["account_number"] == "1234567"
        assert data["holder_kana"] == "カ）フィノラ"

        g = admin_s.get(f"{BASE}/api/payouts/bank").json()
        assert g["bank"]["account_number"] == "1234567"
        assert g["updated_at"]

    @pytest.mark.asyncio
    async def test_stored_encrypted_in_mongo(self, tenant_a_id):
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        doc = await cli[os.environ["DB_NAME"]].tenants.find_one({"id": tenant_a_id})
        pb = doc.get("payout_bank")
        assert pb and pb.get("enc"), "payout_bank.enc missing"
        # plaintext should NOT contain account number
        assert "1234567" not in json.dumps(pb, ensure_ascii=False)
        cli.close()

    @pytest.mark.asyncio
    async def test_audit_masks_account(self, admin_s, tenant_a_id):
        # trigger a fresh PUT to write audit
        admin_s.put(f"{BASE}/api/payouts/bank", json=TEST_BANK)
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        row = await cli[os.environ["DB_NAME"]].audit_logs.find_one(
            {"tenant_id": tenant_a_id, "entity": "payout_bank"}, sort=[("at", -1)])
        assert row is not None
        blob = json.dumps(row, ensure_ascii=False, default=str)
        assert "1234567" not in blob, "account_number leaked to audit_log"
        assert "***4567" in blob, "expected masked ***4567"
        cli.close()


# ---------- 3. Card pay gating ----------

class TestCardGating:
    def test_invoices_card_enabled_true_after_bank(self, admin_s):
        invs = admin_s.get(f"{BASE}/api/invoices").json()
        assert invs, "expected some invoices for FINORA Wealth Partners"
        assert all(i.get("card_enabled") is True for i in invs), "card_enabled should be True once bank is set"

    def test_invoices_card_enabled_false_for_tenant_b(self, admin_b_s):
        invs = admin_b_s.get(f"{BASE}/api/invoices").json()
        for i in invs:
            assert i.get("card_enabled") is False, "tenant B has no bank -> card_enabled must be False"


class TestCheckoutGating:
    @pytest.fixture(scope="class")
    def payable_invoice_id(self, client_s):
        invs = client_s.get(f"{BASE}/api/invoices").json()
        payable = [i for i in invs if i["status"] in ("ISSUED", "PARTIALLY_PAID", "OVERDUE") and i["balance"] > 0]
        if not payable:
            pytest.skip("No payable invoice for client@finora.co.jp")
        return payable[0]["id"]

    def test_checkout_succeeds_or_stripe_error_once_bank_set(self, client_s, payable_invoice_id):
        r = client_s.post(f"{BASE}/api/stripe/checkout/invoice",
                          json={"origin_url": "https://finora.co.jp", "invoice_id": payable_invoice_id})
        # 200 => gating passed and Stripe accepted; 400 => gating passed but LIVE Stripe rejected (acceptable per prompt)
        assert r.status_code in (200, 400), f"Unexpected status {r.status_code}: {r.text}"
        if r.status_code == 200:
            assert r.json().get("checkout_url", "").startswith("http")
        else:
            assert "Stripe" in r.text

    @pytest.mark.asyncio
    async def test_checkout_409_when_no_bank(self, client_s, payable_invoice_id, tenant_a_id):
        # temporarily unset payout_bank
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        col = cli[os.environ["DB_NAME"]].tenants
        prev = (await col.find_one({"id": tenant_a_id})).get("payout_bank")
        try:
            await col.update_one({"id": tenant_a_id}, {"$unset": {"payout_bank": ""}})
            r = client_s.post(f"{BASE}/api/stripe/checkout/invoice",
                              json={"origin_url": "https://finora.co.jp", "invoice_id": payable_invoice_id})
            assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"
        finally:
            if prev:
                await col.update_one({"id": tenant_a_id}, {"$set": {"payout_bank": prev}})
            cli.close()


# ---------- 4. Payout ledger ----------

TEST_TAG = f"TEST_PAYOUT_{uuid.uuid4().hex[:8]}"


class TestPayoutLedger:
    @pytest.fixture(scope="class")
    def seeded(self, tenant_a_id):
        """Seed 2 STRIPE payments in tenant A for ledger tests."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]

        async def _setup():
            inv = await db.invoices.find_one({"tenant_id": tenant_a_id})
            assert inv, "need at least 1 invoice in tenant A"
            p1 = {"id": f"{TEST_TAG}_p1", "tenant_id": tenant_a_id, "client_id": inv["client_id"],
                  "invoice_id": inv["id"], "invoice_number": inv["number"], "date": "2026-01-05",
                  "amount": 100000, "method": "CREDIT_CARD", "source": "STRIPE",
                  "stripe_fee": 3600, "stripe_fee_estimated": False,
                  "created_at": "2026-01-05T00:00:00", "reference": "pi_test_" + TEST_TAG}
            p2 = {"id": f"{TEST_TAG}_p2", "tenant_id": tenant_a_id, "client_id": inv["client_id"],
                  "invoice_id": inv["id"], "invoice_number": inv["number"], "date": "2026-01-10",
                  "amount": 50000, "method": "CREDIT_CARD", "source": "STRIPE",
                  # no stripe_fee -> should be estimated at 3.6%
                  "created_at": "2026-01-10T00:00:00", "reference": "pi_test2_" + TEST_TAG}
            await db.payments.insert_many([p1, p2])
            return {"p1": p1["id"], "p2": p2["id"], "invoice_id": inv["id"]}

        info = asyncio.get_event_loop().run_until_complete(_setup())
        yield info

        async def _cleanup():
            await db.payments.delete_many({"id": {"$regex": f"^{TEST_TAG}"}})
            await db.payouts.delete_many({"note": {"$regex": TEST_TAG}})
            await db.notifications.delete_many({"kind": "payout_sent", "data.label": {"$regex": TEST_TAG}})
            cli.close()

        asyncio.get_event_loop().run_until_complete(_cleanup())

    def test_platform_payouts_lists_tenant(self, admin_s, seeded, tenant_a_id):
        r = admin_s.get(f"{BASE}/api/platform/payouts")
        assert r.status_code == 200
        rows = {t["tenant_id"]: t for t in r.json()["tenants"]}
        assert tenant_a_id in rows
        row = rows[tenant_a_id]
        # p1: 100000 - 3600 = 96400; p2: 50000 - round(50000*0.036)=50000-1800 = 48200 -> total >= 144600 for our two
        # but tenant may have other stripe payments too; check ours are represented.
        our = {i["payment_id"]: i for i in row["items"] if i["payment_id"].startswith(TEST_TAG)}
        assert len(our) == 2
        assert our[f"{TEST_TAG}_p1"]["stripe_fee"] == 3600
        assert our[f"{TEST_TAG}_p1"]["fee_estimated"] is False
        assert our[f"{TEST_TAG}_p1"]["pending"] == 96400
        assert our[f"{TEST_TAG}_p2"]["stripe_fee"] == 1800
        assert our[f"{TEST_TAG}_p2"]["fee_estimated"] is True
        assert our[f"{TEST_TAG}_p2"]["pending"] == 48200

    def test_consultant_forbidden_platform_payouts(self, consultant_s):
        r = consultant_s.get(f"{BASE}/api/platform/payouts")
        assert r.status_code == 403

    def test_mark_sent_409_no_bank_tenant(self, admin_s, tenant_b_id):
        r = admin_s.post(f"{BASE}/api/platform/payouts/{tenant_b_id}",
                         json={"transfer_fee": 0, "transfer_date": "2026-01-20", "note": TEST_TAG})
        assert r.status_code == 409

    def test_mark_sent_creates_payout_and_settles(self, admin_s, seeded, tenant_a_id, client_s):
        pre = admin_s.get(f"{BASE}/api/platform/payouts").json()
        pre_row = next(t for t in pre["tenants"] if t["tenant_id"] == tenant_a_id)
        pre_total = pre_row["total"]
        r = admin_s.post(f"{BASE}/api/platform/payouts/{tenant_a_id}",
                         json={"transfer_fee": 330, "transfer_date": "2026-01-20", "note": TEST_TAG})
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["amount"] == pre_total - 330
        assert doc["bank"]["account_number"].startswith("***")
        assert doc["status"] == "SENT"

        # After settle, pending on our seeded items should be ~0
        post = admin_s.get(f"{BASE}/api/platform/payouts").json()
        post_row = next((t for t in post["tenants"] if t["tenant_id"] == tenant_a_id), None)
        # our items should no longer appear (pending<0.5 filtered out)
        our = [] if post_row is None else [i for i in post_row["items"] if i["payment_id"].startswith(TEST_TAG)]
        assert our == []

        # tenant admin GET /api/payouts returns history
        hist = admin_s.get(f"{BASE}/api/payouts").json()
        ids = [h["id"] for h in hist["history"]]
        assert doc["id"] in ids

    def test_refund_after_payout_creates_negative_pending(self, admin_s, seeded, tenant_a_id):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]

        async def _refund():
            await db.payments.update_one({"id": f"{TEST_TAG}_p1"}, {"$set": {"refunded_amount": 20000}})
        asyncio.get_event_loop().run_until_complete(_refund())
        cli.close()

        r = admin_s.get(f"{BASE}/api/platform/payouts").json()
        row = next((t for t in r["tenants"] if t["tenant_id"] == tenant_a_id), None)
        assert row, "tenant should reappear because of refund"
        our = [i for i in row["items"] if i["payment_id"] == f"{TEST_TAG}_p1"]
        assert len(our) == 1
        # net = 100000 - 20000 - 3600 = 76400; settled was 96400; pending = 76400-96400 = -20000
        assert our[0]["pending"] == -20000


# ---------- 5. Regression: _fulfill's record_fee ----------

class TestFulfillRecordFee:
    @pytest.mark.asyncio
    async def test_record_fee_fallback_estimate(self):
        """Directly exercise payouts.record_fee — pi=None (or invalid) must store an estimated fee."""
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        pid = f"{TEST_TAG}_fee_probe"
        await db.payments.insert_one({"id": pid, "tenant_id": "x", "amount": 25000, "source": "STRIPE"})
        try:
            from payouts import record_fee
            await record_fee(pid, None, 25000)
            doc = await db.payments.find_one({"id": pid})
            assert doc["stripe_fee"] == 900  # round(25000 * 0.036)
            assert doc["stripe_fee_estimated"] is True
        finally:
            await db.payments.delete_one({"id": pid})
            cli.close()
