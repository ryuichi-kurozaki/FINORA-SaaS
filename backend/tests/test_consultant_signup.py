"""Verify public signup creates admin+is_consultant users; /auth/me exposes flag; existing demo roles unaffected."""
import os
import random
import string
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://investment-hub-309.preview.emergentagent.com").rstrip("/")


def _rand():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


@pytest.fixture(scope="module")
def signup_user():
    email = f"qa-consultant-{_rand()}@example.com"
    password = "Passw0rd!QA"
    r = requests.post(f"{BASE_URL}/api/public/signup", json={
        "name": "QA Consultant",
        "company_name": "QA Consulting KK",
        "entity_type": "individual",
        "email": email,
        "phone": "090-0000-0000",
        "address": "Tokyo",
        "profile": "test",
        "qualifications": "CFP",
        "plan_code": "TRIAL",
        "password": password,
    })
    assert r.status_code == 200, r.text
    return {"email": email, "password": password, "tenant_id": r.json().get("tenant_id")}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _me(token):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()


def test_signup_creates_admin_with_is_consultant(signup_user):
    token = _login(signup_user["email"], signup_user["password"])
    me = _me(token)
    assert me["role"] == "admin", f"role={me['role']}"
    assert me.get("is_consultant") is True, f"is_consultant={me.get('is_consultant')}"
    assert me["email"] == signup_user["email"]


def test_signup_user_can_access_billing_invoices(signup_user):
    token = _login(signup_user["email"], signup_user["password"])
    # /api/invoices is owner-scoped (admin can list)
    r = requests.get(f"{BASE_URL}/api/invoices", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text


def test_finora_admin_still_plain_admin():
    token = _login("ryuichi.kurozaki@gmail.com", "Finora2026!")
    me = _me(token)
    assert me["role"] == "admin"
    assert not me.get("is_consultant"), f"FINORA admin unexpectedly has is_consultant={me.get('is_consultant')}"


def test_preview_consultant_role_unchanged():
    token = _login("consultant@finora.co.jp", "Finora2026!")
    me = _me(token)
    assert me["role"] == "consultant"
