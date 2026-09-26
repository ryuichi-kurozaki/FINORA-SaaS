"""Test backend error message localization via X-Lang header."""
import os
import requests
import pytest

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL is not set"


def _login_err(lang):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "nobody-qa@example.com", "password": "wrong-password-xyz"},
        headers={"X-Lang": lang} if lang else {},
    )
    return r


class TestInvalidLoginLocalization:
    """POST /api/auth/login with wrong password should return localized detail per X-Lang."""

    def test_ja_default(self):
        r = _login_err("ja")
        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "メールアドレスまたはパスワードが正しくありません"

    def test_en(self):
        r = _login_err("en")
        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "Invalid email or password"

    def test_pt(self):
        r = _login_err("pt")
        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "E-mail ou senha incorretos"

    def test_missing_header_defaults_ja(self):
        r = _login_err(None)
        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "メールアドレスまたはパスワードが正しくありません"

    def test_unknown_header_defaults_ja(self):
        r = _login_err("de")
        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "メールアドレスまたはパスワードが正しくありません"


class TestValidationLocalization:
    """422 validation errors should be a single localized string."""

    def _post(self, lang):
        return requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "not-an-email"},  # missing password + invalid email
            headers={"X-Lang": lang},
        )

    def test_ja(self):
        r = self._post("ja")
        assert r.status_code == 422
        d = r.json()["detail"]
        assert isinstance(d, str)
        assert d.startswith("入力内容を確認してください")

    def test_en(self):
        r = self._post("en")
        assert r.status_code == 422
        d = r.json()["detail"]
        assert isinstance(d, str)
        assert d.startswith("Please check the input")

    def test_pt(self):
        r = self._post("pt")
        assert r.status_code == 422
        d = r.json()["detail"]
        assert isinstance(d, str)
        assert d.startswith("Verifique os dados informados")


class TestRegressionSmoke:
    """Login with valid creds still works in all 3 languages."""

    @pytest.mark.parametrize("lang", ["ja", "en", "pt"])
    def test_admin_login(self, lang):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "ryuichi.kurozaki@gmail.com", "password": "Finora2026!"},
            headers={"X-Lang": lang},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Session cookie should be set
        assert "user" in data or "access_token" in data or r.cookies

    @pytest.mark.parametrize("lang", ["ja", "en", "pt"])
    def test_consultant_login(self, lang):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "consultant@finora.co.jp", "password": "Finora2026!"},
            headers={"X-Lang": lang},
        )
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize("lang", ["ja", "en", "pt"])
    def test_client_login(self, lang):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "client@finora.co.jp", "password": "Finora2026!"},
            headers={"X-Lang": lang},
        )
        assert r.status_code == 200, r.text
