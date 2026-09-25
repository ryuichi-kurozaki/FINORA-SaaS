"""Idempotent v2 migration: task ownership, valuation dates, transactions, goals, daily history, 2nd client login."""
import random
from datetime import datetime, timedelta

from core import db, new_id, now_iso
from analytics import DEFAULT_FX, enrich, summarize
from seed import upsert_user

SHARED_KINDS = {"meeting", "document_deadline", "dividend", "loan_renewal", "insurance_renewal"}


def _d(days):
    return (datetime.now().date() - timedelta(days=days)).isoformat()


async def seed_v2(t, pw, consultant_id):
    tid = t["id"]
    if await db.goals.find_one({"tenant_id": tid}):
        return
    clients = await db.clients.find({"tenant_id": tid}).sort("created_at", 1).to_list(100)
    if len(clients) < 3:
        return
    c1, c3 = clients[0], clients[2]
    await upsert_user(tid, "client2@finora.co.jp", c3.get("name") or "Client 2", "client", pw, c3["id"])
    for task in await db.tasks.find({"tenant_id": tid, "owner_id": {"$exists": False}}).to_list(1000):
        await db.tasks.update_one({"id": task["id"]}, {"$set": {"owner_id": task.get("assignee_id") or consultant_id, "owner_role": "consultant",
                                                                 "visibility": "shared" if task.get("kind") in SHARED_KINDS else "internal"}})
    for i, a in enumerate(await db.assets.find({"tenant_id": tid}).to_list(1000)):
        await db.assets.update_one({"id": a["id"]}, {"$set": {"price_date": _d(45 if i % 6 == 0 else 2), "source": "MANUAL", "updated_by_role": "client"}})
    for l in await db.liabilities.find({"tenant_id": tid}).to_list(1000):
        await db.liabilities.update_one({"id": l["id"]}, {"$set": {"balance_date": _d(120 if l.get("liability_type") == "auto_loan" else 10), "source": "MANUAL", "updated_by_role": "client"}})
    for coll in ("accounts", "cashflows"):
        await db[coll].update_many({"tenant_id": tid}, {"$set": {"source": "MANUAL", "updated_by_role": "client"}})
    await db.settings.update_one({"tenant_id": tid}, {"$set": {"fx_updated_at": now_iso(), "base_currency": "JPY"}}, upsert=True)

    users = {u["client_id"]: u["id"] for u in await db.users.find({"tenant_id": tid, "role": "client"}).to_list(100)}
    base = lambda cid, extra: {"id": new_id(), "tenant_id": tid, "client_id": cid, "created_at": now_iso(), "updated_at": now_iso(),  # noqa: E731
                               "created_by": users.get(cid), "updated_by": users.get(cid), "updated_by_role": "client", "source": "MANUAL", **extra}
    for a in await db.assets.find({"tenant_id": tid, "client_id": c1["id"], "asset_class": {"$in": ["jp_stock", "foreign_stock", "etf"]}}).to_list(100):
        q, p, cur = a.get("quantity") or 0, a.get("acquisition_price") or 0, a.get("currency") or "JPY"
        acq = a.get("acquired_date") or _d(900)
        txs = [("buy", acq, q * 0.6, p * 0.95), ("buy", _d(500), q * 0.5, p * 1.08), ("sell", _d(200), q * 0.1, (a.get("current_price") or p) * 0.97)]
        for typ, date, qty, price in txs:
            await db.transactions.insert_one(base(c1["id"], {"date": date, "account_id": a.get("account_id"), "asset_id": a["id"], "tx_type": typ,
                                                              "quantity": round(qty, 4), "unit_price": round(price, 2), "amount": round(qty * price, 2),
                                                              "currency": cur, "fx_rate": DEFAULT_FX.get(cur, 1), "fee": round(qty * price * 0.001, 2), "tax": 0, "notes": ""}))
        if a.get("dividend_annual"):
            await db.transactions.insert_one(base(c1["id"], {"date": _d(60), "account_id": a.get("account_id"), "asset_id": a["id"], "tx_type": "dividend",
                                                              "quantity": 0, "unit_price": 0, "amount": round(a["dividend_annual"] / 2, 2), "currency": cur,
                                                              "fx_rate": DEFAULT_FX.get(cur, 1), "fee": 0, "tax": round(a["dividend_annual"] / 2 * 0.2, 2), "notes": ""}))
    assets = [enrich(a, DEFAULT_FX) for a in await db.assets.find({"tenant_id": tid, "client_id": c1["id"]}).to_list(500)]
    s = summarize(assets, await db.liabilities.find({"tenant_id": tid, "client_id": c1["id"]}).to_list(100))
    year = datetime.now().year
    for name, cat, target, tdate, pr in [
        ("10年後に純資産を1.8倍", "net_worth", round(s["net_worth"] * 1.8, -6), f"{year + 10}-12-31", "high"),
        ("年間配当・利息 500万円", "dividend", 5_000_000, f"{year + 5}-12-31", "medium"),
        ("借入比率30%以下", "debt_ratio", 30, f"{year + 3}-12-31", "medium"),
        ("住宅ローン完済", "loan_payoff", 0, "2051-03-31", "low"),
    ]:
        await db.goals.insert_one(base(c1["id"], {"name": name, "category": cat, "target_amount": target, "current_value": None,
                                                   "target_date": tdate, "priority": pr, "notes": ""}))
    rnd = random.Random(7)
    for c in clients:
        ca = [enrich(a, DEFAULT_FX) for a in await db.assets.find({"tenant_id": tid, "client_id": c["id"]}).to_list(500)]
        cs = summarize(ca, await db.liabilities.find({"tenant_id": tid, "client_id": c["id"]}).to_list(100))
        docs = []
        for i in range(120, 0, -1):
            f = 0.95 + 0.05 * (120 - i) / 120 + rnd.uniform(-0.006, 0.006)
            ta, tl = cs["total_assets"] * f, cs["total_liabilities"] * (1 + i * 0.0002)
            docs.append({"tenant_id": tid, "client_id": c["id"], "date": _d(i), "total_assets": round(ta), "total_liabilities": round(tl), "net_worth": round(ta - tl)})
        await db.daily_snapshots.insert_many(docs)
    await db.requests.insert_one({"id": new_id(), "tenant_id": tid, "client_id": c1["id"], "category": "portfolio",
                                  "title": "米国株比率の見直しについて相談したい", "content": "為替リスクが気になるため、米国株の比率について相談したいです。",
                                  "status": "accepted", "assignee_id": consultant_id, "created_by": users.get(c1["id"]),
                                  "created_at": now_iso(), "updated_at": now_iso()})
