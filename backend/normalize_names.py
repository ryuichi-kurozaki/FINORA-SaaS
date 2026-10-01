"""One-off: NFKC-normalize asset/transaction names (unify full/half width),
merge width-duplicate holdings per client, then rebuild holdings from transactions and refresh prices."""
import asyncio
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from core import db, now_iso  # noqa: E402
import txlink  # noqa: E402
import pricing  # noqa: E402


def nfkc(s):
    return unicodedata.normalize("NFKC", s) if isinstance(s, str) else s


async def main():
    # 1) normalize asset names
    norm = 0
    async for a in db.assets.find({}):
        n2 = nfkc(a.get("name"))
        if n2 is not None and n2 != a.get("name"):
            await db.assets.update_one({"id": a["id"]}, {"$set": {"name": n2, "updated_at": now_iso()}})
            norm += 1
    # 1b) normalize transaction notes (keep the ／ separator used for name/type)
    tnorm = 0
    async for tx in db.transactions.find({}):
        notes = tx.get("notes") or ""
        if "／" in notes:
            head, _, rest = notes.partition("／")
            new = nfkc(head) + "／" + rest
        else:
            new = nfkc(notes)
        if new != notes:
            await db.transactions.update_one({"id": tx["id"]}, {"$set": {"notes": new, "updated_at": now_iso()}})
            tnorm += 1

    # 2) merge duplicate holdings that are identical after normalization
    groups = {}
    async for a in db.assets.find({}):
        groups.setdefault((a.get("tenant_id"), a.get("client_id"), a.get("name")), []).append(a)
    merged = 0
    tenants = set()
    for (tenant_id, _cid, _name), rows in groups.items():
        if len(rows) < 2:
            continue
        tenants.add(tenant_id)
        counts = {r["id"]: await db.transactions.count_documents({"asset_id": r["id"]}) for r in rows}
        # primary: has ticker > more linked transactions > most recently updated
        primary = max(rows, key=lambda r: ((r.get("ticker") or "").strip() != "", counts[r["id"]], r.get("updated_at") or ""))
        for r in rows:
            if r["id"] == primary["id"]:
                continue
            await db.transactions.update_many({"asset_id": r["id"]}, {"$set": {"asset_id": primary["id"], "updated_at": now_iso()}})
            await db.assets.delete_one({"id": r["id"]})
            merged += 1

    print("asset_names_normalized", norm, "tx_notes_normalized", tnorm, "assets_merged", merged)

    # 3) rebuild holdings from transactions + refresh prices for affected tenants
    if not tenants:
        tenants = {a["tenant_id"] async for a in db.assets.find({}, {"tenant_id": 1})}
    for t in tenants:
        print("rebuild", t, await txlink.rebuild(tenant_id=t))
    print("price_sync", await pricing.sync())


asyncio.run(main())
