"""Isolated public demo tenant for production (one-click demo logins). Demo users cannot change credentials, pay, refund or upload."""
from core import db, new_id, now_iso
from seed import upsert_user, seed_demo
from seed_v2 import seed_v2
from seed_v3 import seed_v3

SLUG = "finora-showcase"


async def seed_showcase(pw):
    t = await db.tenants.find_one({"slug": SLUG})
    if not t:
        t = {"id": new_id(), "slug": SLUG, "name": "FINORA デモ・ウェルスパートナーズ", "plan": "premium", "demo": True, "created_at": now_iso()}
        await db.tenants.insert_one(t)
    tid = t["id"]
    admin = await upsert_user(tid, "demo-admin@finora.co.jp", "デモ 管理者", "admin", pw)
    cons = await upsert_user(tid, "demo-consultant@finora.co.jp", "田中 翔（デモ）", "consultant", pw)
    if not await db.clients.find_one({"tenant_id": tid}):
        cids = await seed_demo(tid, cons["id"], admin["id"])
        await upsert_user(tid, "demo-client@finora.co.jp", "佐藤 健一（デモ）", "client", pw, cids[0])
    await seed_v2(t, pw, cons["id"], client2_email="demo-client2@finora.co.jp")
    await seed_v3(t, pw, platform=False, tenant_b=False)
    await db.users.update_many({"tenant_id": tid}, {"$set": {"demo": True, "platform_admin": False}})
