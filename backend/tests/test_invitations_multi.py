"""Iter16: Client invitations with email + WhatsApp delivery + resend + scope."""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

ADMIN = ("ryuichi.kurozaki@gmail.com", "Finora2026!")
CONS = ("consultant@finora.co.jp", "Finora2026!")
CONS_B = ("consultantb@finora.co.jp", "Finora2026!")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}"
    j = r.json()
    return j.get("access_token") or j.get("token")


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def consb_tok():
    return _login(*CONS_B)


@pytest.fixture(scope="module")
def test_client(admin_tok):
    # Create a fresh client in tenant A (admin) with whatsapp so prefill can be tested
    payload = {"name": f"TEST_INV_{uuid.uuid4().hex[:6]}",
               "email": f"TEST_inv_{uuid.uuid4().hex[:6]}@example.com",
               "whatsapp": "090-1234-5678",
               "date_of_birth": "1990-01-01"}
    r = requests.post(f"{API}/data/clients", headers=_h(admin_tok), json=payload, timeout=20)
    assert r.status_code in (200, 201), r.text
    c = r.json()
    yield c
    # Teardown: cancel any pending invites & delete client
    try:
        invs = requests.get(f"{API}/invitations?client_id={c['id']}", headers=_h(admin_tok), timeout=20).json()
        for i in invs:
            if i.get("status") == "PENDING":
                requests.post(f"{API}/invitations/{i['id']}/cancel", headers=_h(admin_tok), timeout=20)
        requests.delete(f"{API}/data/clients/{c['id']}", headers=_h(admin_tok), timeout=20)
    except Exception:
        pass


# --- sign_notify.wa_digits unit test ---
class TestWaDigits:
    def test_wa_digits_formats(self):
        # Reimplement locally to avoid importing DB-connected module in test collection
        import re
        def wa_digits(p):
            d = re.sub(r"\D", "", p or "")
            return "81" + d[1:] if d.startswith("0") and not d.startswith("00") else d.lstrip("0") or None
        assert wa_digits("090-1234-5678") == "819012345678"
        assert wa_digits("+55 11 91234-5678") == "5511912345678"
        assert wa_digits("") is None
        assert wa_digits(None) is None

    def test_wa_digits_via_module(self):
        # Real module import (load backend .env first, stripping quotes)
        import sys, os
        from pathlib import Path
        env = Path("/app/backend/.env")
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                os.environ[k.strip()] = v
        sys.path.insert(0, "/app/backend")
        from sign_notify import wa_digits
        assert wa_digits("090-1234-5678") == "819012345678"
        assert wa_digits("+55 11 91234-5678") == "5511912345678"
        assert wa_digits("") is None


class TestInvitationsAPI:
    def test_create_invitation_email_only(self, admin_tok, test_client):
        # Use example.com so email will FAILED (acceptable) instead of spamming
        email = f"TEST_inv_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/invitations", headers=_h(admin_tok),
                          json={"client_id": test_client["id"], "email": email}, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        # ciphertext + token_hash never returned
        assert "token_hash" not in d
        assert "whatsapp" not in d  # ciphertext
        assert "token" in d and "path" in d
        assert d["path"].startswith("/invite/")
        assert d.get("whatsapp_masked") in (None, "")
        dlv = d["delivery"]
        assert dlv["email"] in ("SENT", "FAILED")
        assert dlv["whatsapp"] == "SKIPPED"
        assert "at" in dlv

    def test_create_invitation_with_whatsapp_and_list_hides_ciphertext(self, admin_tok, test_client):
        wa = "090-1234-5678"
        email = f"TEST_inv_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/invitations", headers=_h(admin_tok),
                          json={"client_id": test_client["id"], "email": email, "whatsapp": wa}, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["whatsapp_masked"] == "***5678"
        assert "whatsapp" not in d
        assert d["delivery"]["whatsapp"] in ("SKIPPED", "FAILED")  # empty WA_URL → SKIPPED

        # List: no ciphertext, includes masked + delivery
        lst = requests.get(f"{API}/invitations?client_id={test_client['id']}",
                          headers=_h(admin_tok), timeout=20).json()
        cur = [i for i in lst if i["id"] == d["id"]][0]
        assert "token_hash" not in cur
        assert "whatsapp" not in cur  # no ciphertext
        assert cur["whatsapp_masked"] == "***5678"
        assert cur["delivery"]["email"] in ("SENT", "FAILED")

    def test_resend_only_pending_or_expired(self, admin_tok, test_client):
        email = f"TEST_inv_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/invitations", headers=_h(admin_tok),
                          json={"client_id": test_client["id"], "email": email, "whatsapp": "090-1234-5678"}, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        old_token = d["token"]
        old_path = d["path"]
        iid = d["id"]

        # Old public endpoint works before resend
        pub = requests.get(f"{API}/public/invitations/{old_token}", timeout=20)
        assert pub.status_code == 200

        # Resend
        rr = requests.post(f"{API}/invitations/{iid}/resend", headers=_h(admin_tok), timeout=45)
        assert rr.status_code == 200, rr.text
        rd = rr.json()
        assert rd["ok"] is True
        assert rd["path"].startswith("/invite/") and rd["path"] != old_path
        assert rd["delivery"]["email"] in ("SENT", "FAILED")

        # Old token no longer works
        pub_old = requests.get(f"{API}/public/invitations/{old_token}", timeout=20)
        assert pub_old.status_code == 404
        # New token works
        new_token = rd["path"].split("/")[-1]
        pub_new = requests.get(f"{API}/public/invitations/{new_token}", timeout=20)
        assert pub_new.status_code == 200

        # resend_count incremented, expires_at extended (list check)
        lst = requests.get(f"{API}/invitations?client_id={test_client['id']}",
                          headers=_h(admin_tok), timeout=20).json()
        cur = [i for i in lst if i["id"] == iid][0]
        assert cur.get("resend_count", 0) >= 1

        # Cancel → cannot resend
        cx = requests.post(f"{API}/invitations/{iid}/cancel", headers=_h(admin_tok), timeout=20)
        assert cx.status_code == 200
        rrr = requests.post(f"{API}/invitations/{iid}/resend", headers=_h(admin_tok), timeout=20)
        assert rrr.status_code == 409

    def test_resend_other_tenant_scope_404(self, admin_tok, consb_tok, test_client):
        email = f"TEST_inv_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/invitations", headers=_h(admin_tok),
                          json={"client_id": test_client["id"], "email": email}, timeout=45)
        assert r.status_code == 200
        iid = r.json()["id"]
        # consultant B (other tenant) tries to resend → 404
        rx = requests.post(f"{API}/invitations/{iid}/resend", headers=_h(consb_tok), timeout=20)
        assert rx.status_code == 404
        # cleanup: cancel
        requests.post(f"{API}/invitations/{iid}/cancel", headers=_h(admin_tok), timeout=20)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
