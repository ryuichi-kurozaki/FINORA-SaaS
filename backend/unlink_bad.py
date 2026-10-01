"""One-off: unlink fund tickers whose refreshed NAV is far from the imported acquisition price (wrong same-family match)."""
import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from core import db, now_iso  # noqa: E402


async def main():
    bad = []
    async for a in db.assets.find({"asset_class": "fund", "ticker": {"$nin": [None, ""]}, "source": "IMPORT"}):
        acq, cur = a.get("acquisition_price") or 0, a.get("current_price") or 0
        if acq and cur and not 0.3 <= cur / acq <= 3:
            bad.append((a["name"], a["ticker"], acq, cur))
            await db.assets.update_one({"id": a["id"]}, {"$set": {"ticker": "", "current_price": acq, "price_date": None, "updated_at": now_iso()}})
    for b in bad:
        print("unlinked", b)
    print("total", len(bad))


asyncio.run(main())
