"""One-off: re-verify tickers of imported funds with the stricter matcher; correct or unlink the wrong ones, then refresh prices."""
import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import pricing  # noqa: E402
from core import db, now_iso  # noqa: E402


async def main():
    cache = {}
    changed = []
    async for a in db.assets.find({"asset_class": "fund", "source": "IMPORT"}):
        name, old = a.get("name"), (a.get("ticker") or "").strip()
        if not name:
            continue
        if name not in cache:
            cache[name] = await pricing.match_ticker(name)
        new = cache[name] or ""
        if new == old:
            continue
        upd = {"ticker": new, "updated_at": now_iso()}
        if not new:
            upd["current_price"] = a.get("acquisition_price") or a.get("current_price")
            upd["price_date"] = None
        await db.assets.update_one({"id": a["id"]}, {"$set": upd})
        changed.append((name[:40], old or "-", new or "-"))
    for c in changed:
        print("relinked", c)
    print("changed", len(changed))
    print(await pricing.sync())


asyncio.run(main())
