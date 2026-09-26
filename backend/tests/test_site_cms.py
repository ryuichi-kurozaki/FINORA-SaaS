"""Backend tests for Site CMS (public + platform admin) — iteration 20."""
import io
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://investment-hub-309.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "ryuichi.kurozaki@gmail.com", "password": "Finora2026!"}
CONSULTANT = {"email": "consultant@finora.co.jp", "password": "Finora2026!"}


def _login(sess, creds):
    r = sess.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    _login(s, ADMIN)
    return s


@pytest.fixture(scope="module")
def consultant_sess():
    s = requests.Session()
    _login(s, CONSULTANT)
    return s


# ----------- Public endpoints -----------
class TestPublicSite:
    def test_public_site_ja(self):
        r = requests.get(f"{API}/public/site?lang=ja", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("settings", "services", "faqs", "history", "news"):
            assert k in d
        assert isinstance(d["settings"].get("company_name"), str) and d["settings"]["company_name"]
        # news limited to 5
        assert len(d["news"]) <= 5
        # services/faqs/history should be populated by seed
        assert len(d["services"]) >= 1
        assert len(d["faqs"]) >= 1
        assert len(d["history"]) >= 1

    def test_public_site_en_fallback(self):
        r = requests.get(f"{API}/public/site?lang=en", timeout=15)
        assert r.status_code == 200
        s = r.json()["settings"]
        # english seeded → not empty
        assert s["company_name"]

    def test_public_site_pt(self):
        r = requests.get(f"{API}/public/site?lang=pt", timeout=15)
        assert r.status_code == 200
        assert r.json()["settings"]["company_name"]

    def test_public_news_list_and_category_filter(self):
        r = requests.get(f"{API}/public/site/news?lang=ja", timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        cats = {i.get("category") for i in items}
        # notice + press exist per seed
        # take a category to filter with
        cat = next(iter([c for c in cats if c]), "notice")
        r2 = requests.get(f"{API}/public/site/news?lang=ja&category={cat}", timeout=15)
        assert r2.status_code == 200
        for i in r2.json():
            assert i["category"] == cat

    def test_public_news_item_and_unknown_404(self):
        items = requests.get(f"{API}/public/site/news?lang=ja", timeout=15).json()
        nid = items[0]["id"]
        r = requests.get(f"{API}/public/site/news/{nid}?lang=ja", timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == nid
        # unknown
        r404 = requests.get(f"{API}/public/site/news/does-not-exist?lang=ja", timeout=15)
        assert r404.status_code == 404


# ----------- Auth / Access control -----------
class TestAccessControl:
    def test_platform_site_requires_platform_admin(self, consultant_sess):
        r = consultant_sess.get(f"{API}/platform/site", timeout=15)
        assert r.status_code == 403

    def test_platform_upload_requires_platform_admin(self, consultant_sess):
        files = {"file": ("t.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")}
        r = consultant_sess.post(f"{API}/platform/site/upload", files=files, timeout=15)
        assert r.status_code == 403

    def test_platform_site_admin_ok(self, admin_sess):
        r = admin_sess.get(f"{API}/platform/site", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "settings" in d and "items" in d
        # no mongo _id leaking
        for it in d["items"][:5]:
            assert "_id" not in it


# ----------- Upload validation -----------
class TestUpload:
    def test_upload_rejects_non_image(self, admin_sess):
        files = {"file": ("t.txt", b"hello world", "text/plain")}
        r = admin_sess.post(f"{API}/platform/site/upload", files=files, timeout=15)
        assert r.status_code == 422

    def test_upload_rejects_too_large(self, admin_sess):
        big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10)
        files = {"file": ("big.png", big, "image/png")}
        r = admin_sess.post(f"{API}/platform/site/upload", files=files, timeout=30)
        assert r.status_code == 413

    def test_upload_accepts_png_and_serves(self, admin_sess):
        data = b"\x89PNG\r\n\x1a\n" + b"0" * 50
        files = {"file": ("small.png", data, "image/png")}
        r = admin_sess.post(f"{API}/platform/site/upload", files=files, timeout=15)
        assert r.status_code == 200
        url = r.json()["url"]
        assert url.startswith("/api/public/site/files/")
        # fetch
        r2 = requests.get(f"{BASE}{url}", timeout=15)
        assert r2.status_code == 200


# ----------- Admin CRUD + reflect on public -----------
class TestAdminItemsCRUD:
    def test_create_edit_delete_news(self, admin_sess):
        payload = {
            "kind": "news",
            "title": {"ja": "TEST_iter20 テストお知らせ", "en": "TEST_iter20 news", "pt": ""},
            "body": {"ja": "本文", "en": "body", "pt": ""},
            "date": "2026-01-15",
            "category": "notice",
            "order": 0,
            "published": True,
        }
        r = admin_sess.post(f"{API}/platform/site/items", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        item = r.json()
        iid = item["id"]
        try:
            # Should show up in public news
            pub = requests.get(f"{API}/public/site/news?lang=ja", timeout=15).json()
            assert any(x["id"] == iid for x in pub)

            # missing ja title -> 422
            bad = {**payload, "title": {"ja": "", "en": "x", "pt": ""}}
            r_bad = admin_sess.post(f"{API}/platform/site/items", json=bad, timeout=15)
            assert r_bad.status_code == 422

            # invalid category -> 422
            bad2 = {**payload, "category": "bogus"}
            r_bad2 = admin_sess.post(f"{API}/platform/site/items", json=bad2, timeout=15)
            assert r_bad2.status_code == 422

            # Update — unpublish, should disappear from public
            upd = {**payload, "published": False, "title": {"ja": "TEST_iter20 更新済み", "en": "u", "pt": ""}}
            r_u = admin_sess.put(f"{API}/platform/site/items/{iid}", json=upd, timeout=15)
            assert r_u.status_code == 200
            pub2 = requests.get(f"{API}/public/site/news?lang=ja", timeout=15).json()
            assert not any(x["id"] == iid for x in pub2)
            # unpublished item 404 on public detail
            r_pd = requests.get(f"{API}/public/site/news/{iid}?lang=ja", timeout=15)
            assert r_pd.status_code == 404
        finally:
            r_d = admin_sess.delete(f"{API}/platform/site/items/{iid}", timeout=15)
            assert r_d.status_code == 200

    def test_settings_update_and_reflect(self, admin_sess):
        # Get current settings
        cur = admin_sess.get(f"{API}/platform/site", timeout=15).json()["settings"]
        original_phone = cur.get("phone", {"ja": "", "en": "", "pt": ""})
        try:
            new_data = {**cur, "phone": {"ja": "03-9999-9999 TEST", "en": "+81-3-9999-9999 TEST", "pt": "+81-3-9999-9999 TEST"}}
            r = admin_sess.put(f"{API}/platform/site/settings", json={"data": new_data}, timeout=15)
            assert r.status_code == 200
            pub = requests.get(f"{API}/public/site?lang=ja", timeout=15).json()
            assert "TEST" in pub["settings"]["phone"]
        finally:
            # restore
            admin_sess.put(f"{API}/platform/site/settings", json={"data": {**cur, "phone": original_phone}}, timeout=15)


# ----------- Inquiry (should save even if email undeliverable in preview) -----------
class TestInquiry:
    def test_public_inquiry_saved(self):
        payload = {
            "name": "TEST_iter20 テスト",
            "email": "qa+iter20@example.com",
            "message": "iter20 test inquiry — should save regardless of email delivery",
            "phone": "090-0000-0000",
            "company": "QA",
        }
        r = requests.post(f"{API}/public/inquiries", json=payload, timeout=20)
        # ok even though email provider likely rejects info@finora.co.jp
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body.get("ok") is True or "id" in body
