"""Link imported transactions to holdings by security name, then rebuild holding quantity / acquisition cost from them."""
import logging
import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from calc import positions
from core import db, new_id, now_iso, current
from pricing import _scoped, match_ticker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/txlink")
LINKED_TYPES = {"buy", "sell", "dividend", "interest"}
_NOISE = re.compile(r"[\s　・/／\-－‐（）()＜＞<>\[\]「」【】,，.。]+")


def _key(s):
    s = unicodedata.normalize("NFKC", s or "").upper()
    s = re.sub(r"《.*?》|〈.*?〉|【.*?】", "", s).replace("ファンド", "F")
    return _NOISE.sub("", s)


def _tx_name(tx):
    """CSV importers keep the security name in notes ("名称／取引区分" for Okasan, plain name for Rakuten)."""
    return (tx.get("notes") or "").split("／")[0].strip()


async def rebuild(tenant_id=None, client_id=None):
    q = {}
    if tenant_id:
        q["tenant_id"] = tenant_id
    if client_id:
        q["client_id"] = client_id
    txs = await db.transactions.find(q).to_list(20000)
    assets = await db.assets.find(q).to_list(5000)
    by_key = {}
    for a in assets:
        by_key.setdefault((a.get("client_id"), _key(a.get("name"))), a)
    linked = created = rebuilt = 0
    for tx in txs:
        if tx.get("asset_id") or tx.get("tx_type") not in LINKED_TYPES:
            continue
        name = _tx_name(tx)
        if not name:
            continue
        k = (tx.get("client_id"), _key(name))
        a = by_key.get(k)
        if not a:
            a = {"id": new_id(), "tenant_id": tx["tenant_id"], "client_id": tx.get("client_id"), "account_id": tx.get("account_id"),
                 "asset_class": "fund", "name": name[:200], "ticker": await match_ticker(name) or "", "currency": tx.get("currency") or "JPY",
                 "quantity": 0.0, "acquisition_price": 0.0, "current_price": 0.0, "price_unit": 10000,
                 "notes": "取引履歴から自動作成", "source": "IMPORT", "created_at": now_iso(), "updated_at": now_iso()}
            await db.assets.insert_one(dict(a))
            by_key[k] = a
            assets.append(a)
            created += 1
        await db.transactions.update_one({"id": tx["id"]}, {"$set": {"asset_id": a["id"], "updated_at": now_iso()}})
        tx["asset_id"] = a["id"]
        linked += 1
    amap = {a["id"]: a for a in assets}
    for p in positions(txs, assets):
        a = amap.get(p["asset_id"])
        if not a or p["qty"] <= 0:
            continue
        unit = a.get("price_unit") or 1
        upd = {"quantity": round(p["qty"], 4), "acquisition_price": round(p["avg_cost"] * unit, 4), "updated_at": now_iso()}
        if abs((a.get("quantity") or 0) - upd["quantity"]) < 1e-6 and abs((a.get("acquisition_price") or 0) - upd["acquisition_price"]) < 1e-4:
            continue
        await db.assets.update_one({"id": a["id"]}, {"$set": upd})
        rebuilt += 1
    return {"transactions": len(txs), "linked": linked, "created_assets": created, "rebuilt": rebuilt}


@router.post("/rebuild")
async def rebuild_now(client_id: Optional[str] = None, user=Depends(current)):
    cid = await _scoped(user, client_id)
    if not cid and user["role"] != "admin":
        raise HTTPException(422, "Select a client first")
    return await rebuild(user["tenant_id"], cid)
