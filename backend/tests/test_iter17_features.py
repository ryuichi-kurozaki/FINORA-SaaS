"""Iter17: WA health, invoice-issue notify, invitation auto-remind."""
import os
import sys
import asyncio
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from datetime import datetime, timedelta
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://investment-hub-309.preview.emergentagent.com").rstrip("/")
sys.path.insert(0, "/app/backend")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    return tok, j.get("user") or {}


@pytest.fixture(scope="module")
def admins():
    at, au = _login("ryuichi.kurozaki@gmail.com", "Finora2026!")
    bt, bu = _login("consultantb@finora.co.jp", "Finora2026!")
    ct, cu = _login("consultant@finora.co.jp", "Finora2026!")
    clt, clu = _login("client@finora.co.jp", "Finora2026!")
    return {"ryuichi": (at, au), "consultantb": (bt, bu), "consultant": (ct, cu), "client": (clt, clu)}


# === WA Health ===
class TestWaHealth:
    def test_platform_admin_gets_detail(self, admins):
        tok, _ = admins["ryuichi"]
        r = requests.get(f"{BASE_URL}/api/system/wa-health", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert set(["configured", "ok", "since", "checked_at", "detail"]).issubset(j.keys())
        assert j["configured"] is True
        assert j["ok"] is False, f"expected down state in preview: {j}"
        # platform_admin => detail is not None (unreachable message)
        assert j["detail"] is not None and isinstance(j["detail"], str)

    def test_tenant_admin_no_detail(self, admins):
        tok, _ = admins["consultantb"]
        r = requests.get(f"{BASE_URL}/api/system/wa-health", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is False
        assert j["detail"] is None, f"tenant admin should not see detail, got {j['detail']}"

    def test_consultant_forbidden(self, admins):
        tok, _ = admins["consultant"]
        r = requests.get(f"{BASE_URL}/api/system/wa-health", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r.status_code == 403, r.text

    def test_client_forbidden(self, admins):
        tok, _ = admins["client"]
        r = requests.get(f"{BASE_URL}/api/system/wa-health", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r.status_code == 403, r.text


# === wa_health.check() logic (module import, monkeypatched) ===
class TestWaHealthCheck:
    def test_check_transitions(self):
        import wa_health
        from core import db

        # Snapshot state
        original = asyncio.get_event_loop().run_until_complete(db.system_state.find_one({"id": "wa_health"})) if False else None

        async def run():
            orig = await db.system_state.find_one({"id": "wa_health"}) or {}
            mail_calls = []

            async def fake_mail(ok, detail):
                mail_calls.append({"ok": ok, "detail": detail})

            wa_health._mail = fake_mail

            # Case A: starts healthy (prev.ok true assumed) then goes down. Reset to healthy baseline.
            await db.system_state.update_one({"id": "wa_health"}, {"$set": {"ok": True, "fails": 0, "detail": None}}, upsert=True)

            async def probe_fail():
                return False, "test-fail"
            wa_health.probe = probe_fail

            # first fail: should NOT mark down (fails=1)
            r1 = await wa_health.check()
            assert r1["ok"] is True and r1["fails"] == 1
            assert len(mail_calls) == 0, "should not mail on first fail"

            # second fail: transitions to down, should mail
            r2 = await wa_health.check()
            assert r2["ok"] is False and r2["fails"] == 2
            assert len(mail_calls) == 1 and mail_calls[0]["ok"] is False

            # third fail while still down: no additional mail
            r3 = await wa_health.check()
            assert r3["ok"] is False
            assert len(mail_calls) == 1, "no repeat mail while still down"

            # recovery: probe ok -> should mail down->ok
            async def probe_ok():
                return True, ""
            wa_health.probe = probe_ok
            r4 = await wa_health.check()
            assert r4["ok"] is True and r4["fails"] == 0
            assert len(mail_calls) == 2 and mail_calls[1]["ok"] is True

            # subsequent healthy: no mail
            r5 = await wa_health.check()
            assert r5["ok"] is True
            assert len(mail_calls) == 2, "no mail while still healthy"

            # Case B: first check ever healthy shouldn't mail. Wipe key.
            await db.system_state.delete_one({"id": "wa_health"})
            mail_calls.clear()
            r6 = await wa_health.check()
            assert r6["ok"] is True
            assert len(mail_calls) == 0, "no mail when first check healthy (no prev state)"

            # Restore preview-down state per task requirement
            await db.system_state.update_one(
                {"id": "wa_health"},
                {"$set": {"ok": False, "fails": 9, "detail": "unreachable (ConnectError)", "checked_at": wa_health.now_iso(), "since": wa_health.now_iso()}},
                upsert=True,
            )

        asyncio.get_event_loop().run_until_complete(run())


# === Invitation auto reminder ===
class TestReminderScan:
    def test_remind_3d_and_6d(self, admins):
        import tenancy
        from core import db, new_id, now_iso, encrypt
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        import hashlib
        import secrets

        tok, admin_u = admins["ryuichi"]

        async def run():
            # Pick any client of tenant
            tenant_id = admin_u["tenant_id"]
            uid = admin_u["id"]
            cli = await db.clients.find_one({"tenant_id": tenant_id}, {"id": 1})
            assert cli, "need at least one client"
            # Insert invitation created 3.5 days ago
            iid = new_id()
            token = secrets.token_urlsafe(24)
            created = (_dt.now(_tz.utc) - _td(days=3, hours=12)).isoformat()
            doc = {
                "id": iid, "tenant_id": tenant_id, "client_id": cli["id"],
                "email": f"ryuichi.kurozaki+qa17a@gmail.com", "channel": "email",
                "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "invited_by": uid, "invited_by_name": admin_u.get("name") or "T",
                "status": "PENDING", "created_at": created,
                "expires_at": (_dt.fromisoformat(created) + _td(days=7)).isoformat(),
                "reminders_sent": 0,
            }
            await db.invitations.insert_one(doc)

            # Verify old link works
            r_old = requests.get(f"{BASE_URL}/api/public/invitations/{token}", timeout=30)
            assert r_old.status_code == 200

            # Trigger reminder via API (platform admin only)
            r = requests.post(f"{BASE_URL}/api/invitations/reminders/run",
                              headers={"Authorization": f"Bearer {tok}"}, timeout=60)
            assert r.status_code == 200, r.text
            sent = r.json().get("sent", [])
            ids = [s["id"] for s in sent]
            assert iid in ids, f"expected {iid} reminded, got {sent}"
            match = next(s for s in sent if s["id"] == iid)
            assert match["reminder"] == 1

            # Old token now 404
            r_old2 = requests.get(f"{BASE_URL}/api/public/invitations/{token}", timeout=30)
            assert r_old2.status_code == 404, r_old2.status_code

            inv2 = await db.invitations.find_one({"id": iid})
            assert inv2["reminders_sent"] == 1
            assert inv2.get("last_reminded_at")

            # Immediate second call -> no additional reminder (not yet 6d since creation)
            r2 = requests.post(f"{BASE_URL}/api/invitations/reminders/run",
                               headers={"Authorization": f"Bearer {tok}"}, timeout=60)
            sent2 = [s["id"] for s in r2.json().get("sent", [])]
            assert iid not in sent2, "should not double-remind before 6d"

            # Move created_at back to 6.5 days ago; call again -> reminder #2
            new_created = (_dt.now(_tz.utc) - _td(days=6, hours=12)).isoformat()
            await db.invitations.update_one({"id": iid}, {"$set": {"created_at": new_created}})
            r3 = requests.post(f"{BASE_URL}/api/invitations/reminders/run",
                               headers={"Authorization": f"Bearer {tok}"}, timeout=60)
            sent3 = r3.json().get("sent", [])
            m3 = next((s for s in sent3 if s["id"] == iid), None)
            assert m3 and m3["reminder"] == 2, f"expected 2nd reminder, got {sent3}"

            inv3 = await db.invitations.find_one({"id": iid})
            assert inv3["reminders_sent"] == 2

            # Third call: never a 3rd reminder
            r4 = requests.post(f"{BASE_URL}/api/invitations/reminders/run",
                               headers={"Authorization": f"Bearer {tok}"}, timeout=60)
            sent4 = [s["id"] for s in r4.json().get("sent", [])]
            assert iid not in sent4, "must never do 3rd reminder"

            # Cleanup
            await db.invitations.update_one({"id": iid}, {"$set": {"status": "CANCELLED"}})

        asyncio.get_event_loop().run_until_complete(run())

    def test_run_reminders_requires_platform_admin(self, admins):
        tok, _ = admins["consultantb"]  # tenant admin, NOT platform admin
        r = requests.post(f"{BASE_URL}/api/invitations/reminders/run",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r.status_code == 403, r.status_code


# === Invoice issue delivery ===
class TestInvoiceIssueNotify:
    def test_issue_stores_delivery(self, admins):
        tok, admin_u = admins["ryuichi"]
        h = {"Authorization": f"Bearer {tok}"}
        # Find a client with a consultant
        r = requests.get(f"{BASE_URL}/api/data/clients", headers=h, timeout=30)
        assert r.status_code == 200
        clients = r.json()
        # Prefer client having users
        c = clients[0]
        # Create draft invoice
        payload = {
            "client_id": c["id"],
            "items": [{"description": "TEST_iter17 delivery", "quantity": 1, "unit_price": 1000}],
            "tax_rate": 10, "tax_mode": "exclusive"
        }
        rc = requests.post(f"{BASE_URL}/api/invoices", headers=h, json=payload, timeout=30)
        assert rc.status_code == 200, rc.text
        inv = rc.json()
        iid = inv["id"]
        try:
            ri = requests.post(f"{BASE_URL}/api/invoices/{iid}/issue", headers=h, timeout=60)
            assert ri.status_code == 200, ri.text
            issued = ri.json()
            assert issued["status"] in ("ISSUED", "OVERDUE", "PARTIALLY_PAID", "PAID")
            d = issued.get("issue_delivery") or {}
            # Sanity: keys present, at set
            assert "email" in d and "whatsapp" in d and "at" in d, d
            assert d["email"] in ("SENT", "FAILED", "SKIPPED")
            assert d["whatsapp"] in ("SENT", "FAILED", "SKIPPED")
            # In preview WHATSAPP_SERVICE_URL=127.0.0.1:3999 → whatsapp is FAILED or SKIPPED
            assert d["whatsapp"] in ("FAILED", "SKIPPED")
        finally:
            # cleanup: cancel invoice
            requests.post(f"{BASE_URL}/api/invoices/{iid}/cancel", headers=h, timeout=30)
