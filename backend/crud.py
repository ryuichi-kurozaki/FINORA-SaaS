from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends

from core import db, now_iso, new_id, clean, encrypt, decrypt, current, staff, admin_only, accessible_ids, scope, audit

router = APIRouter(prefix="/api/data")

ENTITIES = {
    "clients": {"fields": ["client_type", "name", "corporate_name", "email", "phone", "address", "occupation", "business",
                           "family", "related_corps", "annual_income", "income", "investment_experience",
                           "investment_purpose", "risk_tolerance", "consultant_id", "status", "notes"],
                "num": ["annual_income", "income"], "enc": ["phone", "address", "family", "notes"]},
    "accounts": {"fields": ["client_id", "institution", "account_type", "region", "owner_type", "currency", "branch",
                            "account_number", "notes"], "enc": ["account_number"]},
    "assets": {"fields": ["client_id", "account_id", "asset_class", "name", "ticker", "owner_type", "country", "sector",
                          "currency", "acquired_date", "acquisition_price", "quantity", "current_price", "realized_pl",
                          "dividend_annual", "interest_annual", "notes"],
               "num": ["acquisition_price", "quantity", "current_price", "realized_pl", "dividend_annual", "interest_annual"]},
    "liabilities": {"fields": ["client_id", "liability_type", "institution", "owner_type", "original_amount", "balance",
                               "interest_rate", "rate_type", "monthly_payment", "start_date", "term_months",
                               "maturity_date", "collateral", "notes"],
                    "num": ["original_amount", "balance", "interest_rate", "monthly_payment", "term_months"]},
    "cashflows": {"fields": ["client_id", "direction", "category", "name", "amount", "frequency", "owner_type", "notes"],
                  "num": ["amount"]},
    "consulting": {"fields": ["client_id", "kind", "date", "title", "content", "next_action", "status"], "enc": ["content"]},
    "tasks": {"fields": ["client_id", "kind", "title", "due_date", "status", "priority", "assignee_id", "notes"]},
}
CASCADE = ["accounts", "assets", "liabilities", "cashflows", "consulting", "tasks", "snapshots", "documents"]


def cfg(entity):
    if entity not in ENTITIES:
        raise HTTPException(404, "Unknown entity")
    return ENTITIES[entity]


def sanitize(entity, body):
    c, out = cfg(entity), {}
    for k in c["fields"]:
        if k not in body:
            continue
        v = body[k]
        if k in c.get("num", []):
            try:
                v = float(v) if v not in (None, "") else 0.0
            except (TypeError, ValueError):
                raise HTTPException(422, f"{k} must be numeric")
        elif isinstance(v, str):
            v = v.strip()[:5000]
        elif v is not None and not isinstance(v, (int, float, bool)):
            v = str(v)[:5000]
        out[k] = v
    return out


def to_store(entity, d):
    for k in cfg(entity).get("enc", []):
        if k in d:
            d[k] = encrypt(d[k])
    return d


def from_store(entity, d):
    clean(d)
    for k in cfg(entity).get("enc", []):
        if k in d:
            d[k] = decrypt(d[k])
    return d


async def list_query(user, entity, client_id=None):
    if entity == "clients":
        ids = await accessible_ids(user)
        q = {"tenant_id": user["tenant_id"]}
        if ids is not None:
            q["id"] = {"$in": ids}
        return q
    q = await scope(user, client_id)
    if entity == "tasks" and user["role"] == "consultant" and not client_id:
        q = {"tenant_id": user["tenant_id"], "$or": [{"client_id": q["client_id"]}, {"assignee_id": user["id"]}]}
    return q


async def check_write(user, entity, doc):
    if entity == "clients":
        if user["role"] == "consultant" and doc.get("consultant_id") != user["id"]:
            raise HTTPException(403, "No access to this client")
        return
    cid = doc.get("client_id")
    if not cid:
        if entity == "tasks":
            return
        raise HTTPException(422, "client_id is required")
    await scope(user, cid)


async def list_items(user, entity, client_id=None):
    from analytics import get_fx, enrich
    items = await db[entity].find(await list_query(user, entity, client_id)).sort("created_at", -1).to_list(5000)
    items = [from_store(entity, i) for i in items]
    if entity == "assets":
        fx = await get_fx(user["tenant_id"])
        items = [enrich(i, fx) for i in items]
    if entity != "clients":
        names = {c["id"]: c.get("corporate_name") or c.get("name")
                 for c in await db.clients.find({"tenant_id": user["tenant_id"]}, {"id": 1, "name": 1, "corporate_name": 1}).to_list(5000)}
        for i in items:
            i["client_name"] = names.get(i.get("client_id"), "")
    return items


@router.get("/{entity}")
async def list_entity(entity: str, client_id: Optional[str] = None, user=Depends(current)):
    cfg(entity)
    return await list_items(user, entity, client_id)


@router.get("/{entity}/{item_id}")
async def get_entity(entity: str, item_id: str, user=Depends(current)):
    cfg(entity)
    q = await list_query(user, entity)
    doc = await db[entity].find_one({"$and": [q, {"id": item_id}]})
    if not doc:
        raise HTTPException(404, "Not found")
    return from_store(entity, doc)


@router.post("/{entity}")
async def create_entity(entity: str, body: dict, request: Request, user=Depends(staff)):
    data = sanitize(entity, body)
    if entity == "clients" and (user["role"] == "consultant" or not data.get("consultant_id")):
        data["consultant_id"] = data.get("consultant_id") if user["role"] == "admin" else user["id"]
        data["consultant_id"] = data["consultant_id"] or user["id"]
    await check_write(user, entity, data)
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], **data, "created_at": now_iso(), "updated_at": now_iso(),
           "created_by": user["id"]}
    to_store(entity, doc)
    await db[entity].insert_one(doc)
    await audit(user, "create", entity, doc["id"], after=dict(doc), request=request)
    return from_store(entity, dict(doc))


@router.put("/{entity}/{item_id}")
async def update_entity(entity: str, item_id: str, body: dict, request: Request, user=Depends(staff)):
    data = sanitize(entity, body)
    before = await db[entity].find_one({"id": item_id, "tenant_id": user["tenant_id"]})
    if not before:
        raise HTTPException(404, "Not found")
    await check_write(user, entity, before)
    if entity == "clients" and user["role"] == "consultant":
        data.pop("consultant_id", None)
    await check_write(user, entity, {**before, **data})
    to_store(entity, data)
    data["updated_at"] = now_iso()
    await db[entity].update_one({"id": item_id}, {"$set": data})
    after = await db[entity].find_one({"id": item_id})
    await audit(user, "update", entity, item_id, before=dict(before), after=dict(after), request=request)
    return from_store(entity, after)


@router.delete("/{entity}/{item_id}")
async def delete_entity(entity: str, item_id: str, request: Request, user=Depends(staff)):
    cfg(entity)
    before = await db[entity].find_one({"id": item_id, "tenant_id": user["tenant_id"]})
    if not before:
        raise HTTPException(404, "Not found")
    if entity == "clients":
        await admin_only(request)
        for c in CASCADE:
            await db[c].delete_many({"tenant_id": user["tenant_id"], "client_id": item_id})
    else:
        await check_write(user, entity, before)
    await db[entity].delete_one({"id": item_id})
    await audit(user, "delete", entity, item_id, before=dict(before), request=request)
    return {"ok": True}
