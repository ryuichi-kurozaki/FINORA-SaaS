"""FINORA v3 backend tests: multi-tenant isolation, signup, invitations, contracts→invoices→payments, platform admin."""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PW = "Finora2026!"


def login(email, password=PW):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None, None
    tok = r.json().get("access_token")
    return tok, {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def sessions():
    s = {}
    for role, email in [
        ("owner", "ryuichi.kurozaki@gmail.com"),
        ("consultant", "consultant@finora.co.jp"),
        ("client", "client@finora.co.jp"),
        ("client2", "client2@finora.co.jp"),
        ("ownerb", "consultantb@finora.co.jp"),
        ("clientb", "clientb@finora.co.jp"),
    ]:
        tok, hdr = login(email)
        assert hdr, f"login failed for {email}"
        s[role] = hdr
        me = requests.get(f"{BASE}/api/auth/me", headers=hdr).json()
        s[role + "_user"] = me
    return s


# --- basic connectivity ---
def test_root():
    r = requests.get(f"{BASE}/api/")
    assert r.status_code == 200


# ============ TENANT ISOLATION (CRITICAL) ============
class TestTenantIsolation:
    def test_ownerb_cannot_see_tenantA_invoices(self, sessions):
        # tenantA invoices
        a = requests.get(f"{BASE}/api/invoices", headers=sessions["owner"]).json()
        b = requests.get(f"{BASE}/api/invoices", headers=sessions["ownerb"]).json()
        a_ids = {i["id"] for i in a}
        b_ids = {i["id"] for i in b}
        assert a_ids and b_ids
        assert not (a_ids & b_ids), "Cross-tenant invoices leaked!"

    def test_ownerb_404_on_tenantA_invoice(self, sessions):
        a = requests.get(f"{BASE}/api/invoices", headers=sessions["owner"]).json()
        target = a[0]["id"]
        r = requests.get(f"{BASE}/api/invoices/{target}", headers=sessions["ownerb"])
        assert r.status_code == 404

    def test_ownerb_cannot_see_tenantA_contracts(self, sessions):
        a = requests.get(f"{BASE}/api/data/contracts", headers=sessions["owner"]).json()
        b = requests.get(f"{BASE}/api/data/contracts", headers=sessions["ownerb"]).json()
        assert not ({i["id"] for i in a} & {i["id"] for i in b})

    def test_ownerb_cannot_see_tenantA_clients(self, sessions):
        b = requests.get(f"{BASE}/api/data/clients", headers=sessions["ownerb"]).json()
        # tenant B has only 高橋 誠
        assert len(b) == 1
        assert "高橋" in (b[0].get("name") or "") or b[0].get("name") == "高橋 誠"

    def test_ownerb_clients_overview_only_own(self, sessions):
        r = requests.get(f"{BASE}/api/clients/overview", headers=sessions["ownerb"])
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert "高橋" in data[0]["name"]

    def test_ownerb_payments_isolated(self, sessions):
        a = requests.get(f"{BASE}/api/payments", headers=sessions["owner"]).json()
        b = requests.get(f"{BASE}/api/payments", headers=sessions["ownerb"]).json()
        if a and b:
            assert not ({i["id"] for i in a} & {i["id"] for i in b})

    def test_ownerb_invitations_isolated(self, sessions):
        a = requests.get(f"{BASE}/api/invitations", headers=sessions["owner"]).json()
        b = requests.get(f"{BASE}/api/invitations", headers=sessions["ownerb"]).json()
        if a and b:
            assert not ({i["id"] for i in a} & {i["id"] for i in b})

    def test_clientb_cannot_read_tenantA_invoice(self, sessions):
        a = requests.get(f"{BASE}/api/invoices", headers=sessions["owner"]).json()
        target = a[0]["id"]
        r = requests.get(f"{BASE}/api/invoices/{target}", headers=sessions["clientb"])
        assert r.status_code == 404

    def test_client_only_sees_own_non_draft_invoices(self, sessions):
        r = requests.get(f"{BASE}/api/invoices", headers=sessions["client"])
        assert r.status_code == 200
        cid = sessions["client_user"].get("client_id")
        for inv in r.json():
            assert inv["client_id"] == cid
            assert inv["status"] != "DRAFT"

    def test_client_cannot_read_other_client_invoice(self, sessions):
        # get invoice of client2's client
        cid2 = sessions["client2_user"].get("client_id")
        all_inv = requests.get(f"{BASE}/api/invoices", headers=sessions["owner"]).json()
        others = [i for i in all_inv if i["client_id"] == cid2 and i["status"] != "DRAFT"]
        if not others:
            pytest.skip("no invoice on client2 to test cross-client read")
        r = requests.get(f"{BASE}/api/invoices/{others[0]['id']}", headers=sessions["client"])
        assert r.status_code in (403, 404)


# ============ ROLE RBAC ============
class TestRBAC:
    def test_consultant_cannot_post_invoice(self, sessions):
        # find a client the consultant can access
        clients = requests.get(f"{BASE}/api/data/clients", headers=sessions["consultant"]).json()
        assert clients
        r = requests.post(f"{BASE}/api/invoices", headers=sessions["consultant"],
                          json={"client_id": clients[0]["id"], "items": [{"description": "x", "quantity": 1, "unit_price": 1000}]})
        assert r.status_code == 403

    def test_consultant_cannot_post_payment(self, sessions):
        invs = requests.get(f"{BASE}/api/invoices", headers=sessions["consultant"]).json()
        if not invs:
            pytest.skip()
        r = requests.post(f"{BASE}/api/payments", headers=sessions["consultant"],
                          json={"invoice_id": invs[0]["id"], "date": "2026-01-01", "amount": 100})
        assert r.status_code == 403

    def test_consultant_cannot_post_contract(self, sessions):
        clients = requests.get(f"{BASE}/api/data/clients", headers=sessions["consultant"]).json()
        r = requests.post(f"{BASE}/api/data/contracts", headers=sessions["consultant"],
                          json={"client_id": clients[0]["id"], "name": "T", "fee_type": "MONTHLY", "fee": 1000})
        assert r.status_code == 403

    def test_client_cannot_post_invoice(self, sessions):
        cid = sessions["client_user"]["client_id"]
        r = requests.post(f"{BASE}/api/invoices", headers=sessions["client"],
                          json={"client_id": cid, "items": [{"description": "x", "quantity": 1, "unit_price": 100}]})
        assert r.status_code == 403

    def test_consultant_can_view_assigned_invoices(self, sessions):
        r = requests.get(f"{BASE}/api/invoices", headers=sessions["consultant"])
        assert r.status_code == 200
        assert len(r.json()) > 0


# ============ Owner (admin) contract → invoice → payment workflow ============
class TestBillingFlow:
    @pytest.fixture(scope="class")
    def owner_ctx(self):
        _, hdr = login("ryuichi.kurozaki@gmail.com")
        me = requests.get(f"{BASE}/api/auth/me", headers=hdr).json()
        clients = requests.get(f"{BASE}/api/data/clients", headers=hdr).json()
        return {"h": hdr, "user": me, "client_id": clients[0]["id"]}

    def test_full_flow(self, owner_ctx):
        h = owner_ctx["h"]
        # 1. create contract
        cr = requests.post(f"{BASE}/api/data/contracts", headers=h, json={
            "client_id": owner_ctx["client_id"], "name": "TEST_V3_CONTRACT",
            "service_name": "Test svc", "fee_type": "MONTHLY", "fee": 50000, "tax_mode": "exclusive",
            "tax_rate": 10, "status": "ACTIVE", "start_date": "2026-01-01", "payment_terms_days": 30
        })
        assert cr.status_code == 200, cr.text
        contract_id = cr.json()["id"]

        # 2. create invoice from contract → DRAFT with 10% tax exclusive
        ir = requests.post(f"{BASE}/api/invoices", headers=h,
                           json={"client_id": owner_ctx["client_id"], "contract_id": contract_id})
        assert ir.status_code == 200, ir.text
        inv = ir.json()
        assert inv["status"] == "DRAFT"
        assert inv["tax_rate"] == 10
        assert inv["tax_mode"] == "exclusive"
        assert inv["subtotal"] == 50000
        assert inv["tax"] == 5000
        assert inv["total"] == 55000
        assert inv["number"].startswith("INV-")
        iid = inv["id"]

        # 3. issue
        isr = requests.post(f"{BASE}/api/invoices/{iid}/issue", headers=h)
        assert isr.status_code == 200
        assert isr.json()["status"] == "ISSUED"

        # 4. overpayment → 422
        over = requests.post(f"{BASE}/api/payments", headers=h,
                             json={"invoice_id": iid, "date": "2026-01-05", "amount": 999999})
        assert over.status_code == 422

        # 5. partial payment
        p1 = requests.post(f"{BASE}/api/payments", headers=h,
                           json={"invoice_id": iid, "date": "2026-01-05", "amount": 20000})
        assert p1.status_code == 200
        assert p1.json()["status"] == "PARTIALLY_PAID"
        assert p1.json()["paid"] == 20000
        assert p1.json()["balance"] == 35000
        payment_id = p1.json()["payments"][-1]["id"] if p1.json().get("payments") else None

        # 6. full payment
        p2 = requests.post(f"{BASE}/api/payments", headers=h,
                           json={"invoice_id": iid, "date": "2026-01-10", "amount": 35000})
        assert p2.status_code == 200
        assert p2.json()["status"] == "PAID"
        assert p2.json()["balance"] == 0

        # 7. cancel invoice with payments → 409
        cx = requests.post(f"{BASE}/api/invoices/{iid}/cancel", headers=h)
        assert cx.status_code == 409

        # 8. delete a payment → recomputes to PARTIALLY_PAID
        # fetch payment ids
        det = requests.get(f"{BASE}/api/invoices/{iid}", headers=h).json()
        pays = det["payments"]
        assert len(pays) == 2
        dr = requests.delete(f"{BASE}/api/payments/{pays[-1]['id']}", headers=h)
        assert dr.status_code == 200
        det2 = requests.get(f"{BASE}/api/invoices/{iid}", headers=h).json()
        assert det2["status"] in ("PARTIALLY_PAID", "PAID", "OVERDUE")

        # cleanup: delete remaining payments then cancel invoice
        for p in det2["payments"]:
            requests.delete(f"{BASE}/api/payments/{p['id']}", headers=h)
        # after removing payments status becomes ISSUED (or OVERDUE)
        cx2 = requests.post(f"{BASE}/api/invoices/{iid}/cancel", headers=h)
        assert cx2.status_code == 200

        # 9. contract cancel
        requests.put(f"{BASE}/api/data/contracts/{contract_id}", headers=h,
                     json={"client_id": owner_ctx["client_id"], "name": "TEST_V3_CONTRACT",
                           "fee_type": "MONTHLY", "fee": 50000, "status": "CANCELLED"})

    def test_generate_recurring(self, owner_ctx):
        h = owner_ctx["h"]
        r = requests.post(f"{BASE}/api/invoices/generate-recurring", headers=h)
        assert r.status_code == 200
        assert "created" in r.json()

    def test_billing_summary(self, owner_ctx):
        r = requests.get(f"{BASE}/api/billing/summary", headers=owner_ctx["h"])
        assert r.status_code == 200
        d = r.json()
        for k in ("billed_month", "paid_month", "outstanding", "overdue", "monthly"):
            assert k in d
        assert d["overdue_count"] >= 1  # seed has overdue

    def test_consultant_overview(self, sessions):
        r = requests.get(f"{BASE}/api/consultant/overview", headers=sessions["owner"])
        assert r.status_code == 200
        d = r.json()
        for k in ("clients", "active_contract_clients", "meetings_month", "billing"):
            assert k in d

    def test_overdue_detected(self, sessions):
        invs = requests.get(f"{BASE}/api/invoices", headers=sessions["owner"]).json()
        assert any(i["status"] == "OVERDUE" for i in invs), "expected at least one overdue invoice"


# ============ Signup ============
class TestSignup:
    _created_email = None

    def test_signup_creates_tenant_trial(self):
        email = f"test_v3_{uuid.uuid4().hex[:8]}@example.com"
        TestSignup._created_email = email
        r = requests.post(f"{BASE}/api/public/signup", json={
            "name": "Test Owner", "company_name": "TEST_V3_CO", "email": email, "password": "TestPass2026!",
            "plan_code": "TRIAL"
        })
        assert r.status_code == 200, r.text
        tid = r.json()["tenant_id"]

        # login the new owner
        tok, hdr = login(email, "TestPass2026!")
        assert hdr
        me = requests.get(f"{BASE}/api/auth/me", headers=hdr).json()
        assert me["role"] == "admin"
        assert me["tenant_id"] == tid
        assert me["tenant"]["status"] == "TRIAL"

        # zero clients
        cs = requests.get(f"{BASE}/api/data/clients", headers=hdr).json()
        assert cs == []

        # subscription endpoint works
        sr = requests.get(f"{BASE}/api/subscription", headers=hdr)
        assert sr.status_code == 200
        assert sr.json()["subscription"]["plan_code"] == "TRIAL"

    def test_signup_duplicate_email(self):
        assert TestSignup._created_email
        r = requests.post(f"{BASE}/api/public/signup", json={
            "name": "Dup", "email": TestSignup._created_email, "password": "AnotherPass2026!"
        })
        assert r.status_code == 409


# ============ Invitations ============
class TestInvitations:
    def test_invite_flow(self, sessions):
        h = sessions["owner"]
        clients = requests.get(f"{BASE}/api/data/clients", headers=h).json()
        # pick a client for whom we invite a NEW email
        cid = clients[0]["id"]
        email = f"invitee_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{BASE}/api/invitations", headers=h, json={"client_id": cid, "email": email})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "token" in d and d["path"].startswith("/invite/")
        token = d["token"]

        # public info
        info = requests.get(f"{BASE}/api/public/invitations/{token}")
        assert info.status_code == 200
        assert info.json()["email"] == email
        assert info.json()["status"] == "PENDING"

        # accept
        ar = requests.post(f"{BASE}/api/public/invitations/{token}/accept",
                           json={"name": "New Client", "password": "NewClientPass2026!"})
        assert ar.status_code == 200

        # accept again → 410
        ar2 = requests.post(f"{BASE}/api/public/invitations/{token}/accept",
                            json={"name": "X", "password": "XXXXpass2026!"})
        assert ar2.status_code == 410

        # new user can login and is linked to client
        tok, hdr = login(email, "NewClientPass2026!")
        assert hdr
        me = requests.get(f"{BASE}/api/auth/me", headers=hdr).json()
        assert me["role"] == "client"
        assert me["client_id"] == cid


# ============ Platform admin ============
class TestPlatform:
    def test_platform_tenants_counts_only(self, sessions):
        r = requests.get(f"{BASE}/api/platform/tenants", headers=sessions["owner"])
        assert r.status_code == 200
        for t in r.json():
            # counts only, no invoices/payments detail
            for k in ("customers", "members", "status", "plan_code"):
                assert k in t
            # No financial detail fields expected
            assert "invoices" not in t
            assert "payments" not in t

    def test_platform_forbidden_for_consultant(self, sessions):
        r = requests.get(f"{BASE}/api/platform/tenants", headers=sessions["consultant"])
        assert r.status_code == 403

    def test_platform_forbidden_for_ownerb(self, sessions):
        # ownerb is admin of tenant B but not platform_admin
        r = requests.get(f"{BASE}/api/platform/tenants", headers=sessions["ownerb"])
        assert r.status_code == 403

    def test_suspend_and_restore_tenantB(self, sessions):
        # find tenant B
        tenants = requests.get(f"{BASE}/api/platform/tenants", headers=sessions["owner"]).json()
        tb = next(t for t in tenants if "コンサルティング" in (t.get("name") or "") or t.get("owner_email") == "consultantb@finora.co.jp")
        tid_b = tb["id"]
        # suspend
        r = requests.put(f"{BASE}/api/platform/tenants/{tid_b}", headers=sessions["owner"], json={"status": "SUSPENDED"})
        assert r.status_code == 200

        # ownerb login now blocked
        rl = requests.post(f"{BASE}/api/auth/login", json={"email": "consultantb@finora.co.jp", "password": PW})
        assert rl.status_code == 403

        # restore
        rr = requests.put(f"{BASE}/api/platform/tenants/{tid_b}", headers=sessions["owner"], json={"status": "ACTIVE"})
        assert rr.status_code == 200

        # login ok again
        rl2 = requests.post(f"{BASE}/api/auth/login", json={"email": "consultantb@finora.co.jp", "password": PW})
        assert rl2.status_code == 200

    def test_platform_plan_update(self, sessions):
        r = requests.put(f"{BASE}/api/platform/plans/STANDARD", headers=sessions["owner"],
                         json={"price_monthly": 9800})
        assert r.status_code == 200


# ============ Audit / timeline ============
class TestAudit:
    def test_timeline_scoped(self, sessions):
        clients = requests.get(f"{BASE}/api/data/clients", headers=sessions["owner"]).json()
        cid = clients[0]["id"]
        r = requests.get(f"{BASE}/api/timeline", headers=sessions["owner"], params={"client_id": cid})
        assert r.status_code == 200

    def test_audit_logs_tenant_scoped(self, sessions):
        r = requests.get(f"{BASE}/api/security/audit-logs", headers=sessions["owner"])
        assert r.status_code == 200
        # ownerb sees a different set — re-login as ownerb (its session may have been revoked by prior suspend test)
        _, hdrb = login("consultantb@finora.co.jp")
        rb = requests.get(f"{BASE}/api/security/audit-logs", headers=hdrb)
        assert rb.status_code == 200
        a_ids = {x["id"] for x in r.json()}
        b_ids = {x["id"] for x in rb.json()}
        assert not (a_ids & b_ids)
