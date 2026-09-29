import asyncio, os, sys
from dotenv import load_dotenv; load_dotenv()
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
import core, econtract as E

DEF_SVC_JA = "コンサルティングサービス"
DEF_DESC_JA = "月次の資産運用に関するコンサルティングおよび助言業務。詳細は別途協議のうえ定めるものとする。（仮入力：後で編集してください）"


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    core.db = db; E.db = db
    c = await db.econtracts.find_one({"contract_type": "CONSULTING"})
    if not c:
        print("no consulting contract"); return
    c = dict(c)
    c["terms"] = {**c["terms"], "service_name": DEF_SVC_JA, "description": DEF_DESC_JA}
    for lang in ("ja", "en", "pt"):
        ctx = await E._ctx({**c, "lang": lang})
        print(f"[{lang}] service = {ctx['service']}")
        print(f"[{lang}] description = {ctx['description'][:70]}")
    # custom value stays as-is
    c2 = {**c, "terms": {**c["terms"], "service_name": "特別コンサル", "description": "独自の内容"}}
    ctx = await E._ctx({**c2, "lang": "pt"})
    print(f"[pt custom] service = {ctx['service']} (should stay '特別コンサル')")

asyncio.run(main())
