import asyncio, json, os, sys
from dotenv import load_dotenv; load_dotenv()
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
import core
from core import encrypt, now_iso
import econtract as E
from econtract_tpl import build_sections, DOC_TYPES


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    core.db = db
    E.db = db
    c = await db.econtracts.find_one({"contract_type": "CONSULTING"})
    if not c:
        print("no CONSULTING contract"); return
    cu = await db.users.find_one({"id": c.get("consultant_id")}) or {}
    had = bool((cu.get("payout_bank") or {}).get("enc"))
    if not had:
        b = {"bank_name": "みずほ銀行", "bank_code": "0001", "branch_name": "渋谷支店", "branch_code": "123",
             "account_type": "ORDINARY", "account_number": "1234567", "holder_kana": "ｶﾌﾞｼｷｶﾞｲｼﾔﾃｽﾄ"}
        await db.users.update_one({"id": c["consultant_id"]}, {"$set": {"payout_bank": {"enc": encrypt(json.dumps(b, ensure_ascii=False)), "updated_at": now_iso()}}})
        print("TEMP bank set on", c["consultant_id"])
    for lang in ("ja", "en", "pt"):
        ctx = await E._ctx({**c, "lang": lang})
        secs = build_sections(DOC_TYPES["CONSULTING"][1], lang, ctx, c.get("fields"))
        pm = next((s for s in secs if s["key"] == "payment_method"), None)
        print(f"\n=== {lang} :: {pm['title']} ===\n{pm['body']}")
    if not had:
        await db.users.update_one({"id": c["consultant_id"]}, {"$unset": {"payout_bank": ""}})
        print("\nTEMP bank removed (restored)")

asyncio.run(main())
