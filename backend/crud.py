from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends

from core import (track_peak, sees_all, db, now_iso, new_id, clean, encrypt, decrypt, current, admin_only, accessible_ids, scope, audit,
                  notify_other_side, _label)

router = APIRouter(prefix="/api/data")

ENTITIES = {
    "clients": {"fields": ["client_type", "name", "corporate_name", "email", "phone", "address", "occupation", "business",
                           "family", "related_corps", "annual_income", "income", "investment_experience",
                           "investment_purpose", "risk_tolerance", "consultant_id", "secondary_consultant_ids", "status", "notes"],
                "num": ["annual_income", "income"], "enc": ["phone", "address", "family", "notes"]},
    "accounts": {"fields": ["client_id", "institution", "account_type", "region", "owner_type", "currency", "branch",
                            "account_number", "notes"], "enc": ["account_number"]},
    "assets": {"fields": ["client_id", "account_id", "asset_class", "name", "ticker", "owner_type", "country", "sector",
                          "currency", "acquired_date", "acquisition_price", "quantity", "current_price", "realized_pl",
                          "dividend_annual", "interest_annual", "price_date", "balance_date", "notes"],
               "num": ["acquisition_price", "quantity", "current_price", "realized_pl", "dividend_annual", "interest_annual"]},
    "liabilities": {"fields": ["client_id", "liability_type", "institution", "owner_type", "original_amount", "balance",
                               "interest_rate", "rate_type", "monthly_payment", "start_date", "term_months",
                               "maturity_date", "collateral", "balance_date", "notes"],
                    "num": ["original_amount", "balance", "interest_rate", "monthly_payment", "term_months"]},
    "transactions": {"fields": ["client_id", "date", "account_id", "asset_id", "tx_type", "quantity", "unit_price", "amount",
                                "currency", "fx_rate", "fee", "tax", "notes"],
                     "num": ["quantity", "unit_price", "amount", "fx_rate", "fee", "tax"]},
    "goals": {"fields": ["client_id", "name", "category", "target_amount", "current_value", "target_date", "priority", "notes"],
              "num": ["target_amount", "current_value"], "nullable": ["current_value"]},
    "contracts": {"fields": ["client_id", "name", "service_name", "description", "fee_type", "fee", "tax_mode", "tax_rate",
                             "start_date", "end_date", "billing_cycle", "billing_day", "payment_terms_days", "auto_renew", "status", "notes"],
                  "num": ["fee", "tax_rate", "billing_day", "payment_terms_days"]},
    "cashflows": {"fields": ["client_id", "direction", "category", "name", "amount", "frequency", "owner_type", "notes"],
                  "num": ["amount"]},
    "consulting": {"fields": ["client_id", "kind", "date", "title", "content", "next_action", "status"], "enc": ["content"]},
    "tasks": {"fields": ["client_id", "kind", "title", "due_date", "status", "priority", "assignee_id", "visibility", "notes"]},
}
OWNED = {"accounts", "assets", "liabilities", "cashflows", "transactions", "goals"}
STAFF_ENTITIES = {"clients", "consulting", "contracts"}
CASCADE = ["accounts", "assets", "liabilities", "cashflows", "consulting", "tasks", "snapshots", "documents", "transactions",
           "goals", "corrections", "requests", "comments", "saved_snapshots", "daily_snapshots", "contracts", "invoices", "payments", "invitations"]


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
        if k in c.get("nullable", []) and v in (None, ""):
            v = None
        elif k in c.get("num", []):
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
    if entity == "tasks" and not sees_all(user):
        vis = {"$or": [{"owner_id": user["id"]}, {"visibility": "shared"}]}
        if user["role"] != "client" and not client_id:
            return {"tenant_id": user["tenant_id"], "$or": [{"owner_id": user["id"]}, {"$and": [{"client_id": q["client_id"]}, vis]}]}
        return {"$and": [q, vis]}
    return q


async def check_write(user, entity, doc, existing=None):
    if entity in OWNED:
        if user["role"] != "client":
            raise HTTPException(403, "Client-owned data is read-only for staff. Please send a correction request.")
        if not doc.get("client_id") or doc["client_id"] != user.get("client_id"):
            raise HTTPException(403, "No access to this client")
        return
    if entity in STAFF_ENTITIES:
        if user["role"] == "client" or (entity == "contracts" and user["role"] != "admin"):
            raise HTTPException(403, "Forbidden")
        if entity == "clients":
            if not sees_all(user) and doc.get("consultant_id") != user["id"]:
                raise HTTPException(403, "No access to this client")
            return
        if not doc.get("client_id"):
            raise HTTPException(422, "client_id is required")
        await scope(user, doc["client_id"])
        return
    if existing is not None and existing.get("owner_id") != user["id"]:
        raise HTTPException(403, "Only the owner can modify this task")
    if user["role"] == "client" and doc.get("client_id") != user.get("client_id"):
        raise HTTPException(403, "No access to this client")
    if doc.get("client_id"):
        await scope(user, doc["client_id"])


async def after_client_change(user, entity, action, doc):
    if entity == "clients" and action == "create":
        await track_peak(user["tenant_id"])
    if entity == "contracts" and (action == "create" or doc.get("status") in ("ENDED", "CANCELLED", "PAUSED")):
        kind = "contract_new" if action == "create" else "contract_status"
        await notify_other_side(user, doc.get("client_id"), kind, {"label": doc.get("name"), "status": doc.get("status")}, "/billing")
    if user["role"] == "client" and entity in OWNED:
        await notify_other_side(user, doc.get("client_id"), "client_data_updated",
                                {"entity": entity, "action": action, "label": _label(doc)}, f"/clients/{doc.get('client_id')}")


async def list_items(user, entity, client_id=None):
    from analytics import get_fx, enrich
    items = await db[entity].find(await list_query(user, entity, client_id)).sort("created_at", -1).to_list(5000)
    items = [from_store(entity, i) for i in items]
    if entity == "assets":
        fx = await get_fx(user["tenant_id"])
        s = await db.settings.find_one({"tenant_id": user["tenant_id"]}) or {}
        items = [enrich(i, fx) for i in items]
        for i in items:
            i["fx_date"], i["base_currency"] = s.get("fx_updated_at"), s.get("base_currency", "JPY")
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
async def create_entity(entity: str, body: dict, request: Request, user=Depends(current)):
    data = sanitize(entity, body)
    if entity == "clients" and (user["role"] == "consultant" or not data.get("consultant_id")):
        data["consultant_id"] = data.get("consultant_id") if user["role"] == "admin" else user["id"]
        data["consultant_id"] = data["consultant_id"] or user["id"]
    if entity == "tasks":
        data.update(owner_id=user["id"], owner_role=user["role"], visibility=data.get("visibility") or "internal")
    await check_write(user, entity, data)
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], **data, "created_at": now_iso(), "updated_at": now_iso(),
           "created_by": user["id"], "updated_by": user["id"], "updated_by_role": user["role"],
           "source": body.get("_source", "MANUAL") if entity in OWNED else None}
    to_store(entity, doc)
    await db[entity].insert_one(doc)
    await audit(user, "create", entity, doc["id"], after=dict(doc), request=request)
    await after_client_change(user, entity, "create", doc)
    return from_store(entity, dict(doc))


@router.put("/{entity}/{item_id}")
async def update_entity(entity: str, item_id: str, body: dict, request: Request, user=Depends(current)):
    data = sanitize(entity, body)
    before = await db[entity].find_one({"id": item_id, "tenant_id": user["tenant_id"]})
    if not before:
        raise HTTPException(404, "Not found")
    await check_write(user, entity, before, before if entity == "tasks" else None)
    if entity == "clients" and user["role"] == "consultant":
        data.pop("consultant_id", None)
    await check_write(user, entity, {**before, **data}, before if entity == "tasks" else None)
    to_store(entity, data)
    data.update(updated_at=now_iso(), updated_by=user["id"], updated_by_role=user["role"])
    await db[entity].update_one({"id": item_id}, {"$set": data})
    after = await db[entity].find_one({"id": item_id})
    await audit(user, "update", entity, item_id, before=dict(before), after=dict(after), request=request)
    await after_client_change(user, entity, "update", after)
    return from_store(entity, after)


@router.delete("/{entity}/{item_id}")
async def delete_entity(entity: str, item_id: str, request: Request, user=Depends(current)):
    cfg(entity)
    before = await db[entity].find_one({"id": item_id, "tenant_id": user["tenant_id"]})
    if not before:
        raise HTTPException(404, "Not found")
    if entity == "clients":
        await admin_only(request)
        if not sees_all(user) and before.get("consultant_id") != user["id"]:
            raise HTTPException(403, "No access to this client")
        for c in CASCADE:
            await db[c].delete_many({"tenant_id": user["tenant_id"], "client_id": item_id})
    else:
        await check_write(user, entity, before, before if entity == "tasks" else None)
    await db[entity].delete_one({"id": item_id})
    await audit(user, "delete", entity, item_id, before=dict(before), request=request)
    await after_client_change(user, entity, "delete", before)
    return {"ok": True}
