"""Isolated test: seed() must NOT reset an existing user's password_hash when SEED_DEMO != 'true'.

Uses a throwaway Mongo database, dropped at the end.
"""
import asyncio
import os
import sys


def _set_env(seed_demo: str):
    os.environ["MONGO_URL"] = "mongodb://localhost:27017"
    os.environ["DB_NAME"] = "seedtest_tmp"
    os.environ["SEED_DEMO"] = seed_demo
    os.environ["ADMIN_EMAIL"] = "x@example.com"
    os.environ["ADMIN_PASSWORD"] = "OrigPass123!"
    os.environ["DEMO_PASSWORD"] = "DemoPass000!"
    os.environ["JWT_SECRET"] = "37439c476138189f2b5e51e7565d5a742ec4b9c5e2e4552428120ce60aef6bc8"
    os.environ["FIELD_ENCRYPTION_KEY"] = "LblhE_NyTeegHmp3tsXTnsCdcKn5uohw1C3jL2ZKpY8="


async def run():
    sys.path.insert(0, "/app/backend")
    _set_env("false")

    # Import AFTER env is set (core.py reads env at import time)
    from core import db, hash_password, verify_password
    from seed import seed

    # Clean slate
    await db.client.drop_database("seedtest_tmp")

    # 1) First seed with SEED_DEMO=false -> creates admin with ADMIN_PASSWORD
    await seed()
    u = await db.users.find_one({"email": "x@example.com"})
    assert u is not None, "admin should be created"
    assert verify_password("OrigPass123!", u["password_hash"]), "initial password should match ADMIN_PASSWORD"
    print("STEP1 OK: admin created with ADMIN_PASSWORD")

    # 2) Simulate user changing their password
    new_hash = hash_password("NewPass456!")
    await db.users.update_one({"email": "x@example.com"}, {"$set": {"password_hash": new_hash}})
    print("STEP2 OK: user password changed to NewPass456!")

    # 3) Run seed() again with SEED_DEMO=false -> must NOT reset password
    await seed()
    u2 = await db.users.find_one({"email": "x@example.com"})
    assert verify_password("NewPass456!", u2["password_hash"]), (
        "BUG: seed() reset password_hash back to ADMIN_PASSWORD when SEED_DEMO=false"
    )
    assert not verify_password("OrigPass123!", u2["password_hash"]), (
        "BUG: password reverted to OrigPass123!"
    )
    print("STEP3 OK: seed() with SEED_DEMO=false preserved NewPass456!")

    # 4) Switch to SEED_DEMO=true -> the demo self-heal SHOULD reset admin back to ADMIN_PASSWORD
    os.environ["SEED_DEMO"] = "true"
    await seed()
    u3 = await db.users.find_one({"email": "x@example.com"})
    assert verify_password("OrigPass123!", u3["password_hash"]), (
        "demo self-heal did not reset admin password to ADMIN_PASSWORD"
    )
    print("STEP4 OK: SEED_DEMO=true self-heal reset admin to ADMIN_PASSWORD")

    # Cleanup
    await db.client.drop_database("seedtest_tmp")
    print("CLEANUP OK: dropped seedtest_tmp")


def test_seed_does_not_reset_password_in_production_mode():
    asyncio.run(run())


if __name__ == "__main__":
    test_seed_does_not_reset_password_in_production_mode()
    print("ALL PASSED")
