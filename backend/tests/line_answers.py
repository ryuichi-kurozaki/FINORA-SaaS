import asyncio, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import line_service as L
from core import db


async def main():
    for email in ("client@finora.co.jp", "consultant@finora.co.jp"):
        u = await db.users.find_one({"email": email})
        print("=" * 20, email, u["role"])
        for m in ("ヘルプ", "通知", "請求", "契約", "面談", "資産", "xyz"):
            print(f"--- {m}\n{await L._answer(u, m, u.get('lang') or 'ja')}")

asyncio.run(main())
