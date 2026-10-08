from fastapi import APIRouter, Request, HTTPException, Depends

from core import db, current, now_iso, audit
from crud import sanitize, to_store, from_store

router = APIRouter(prefix="/api/me")

# Basic info + contact fields a client may edit about themselves.
# Internal/advisory fields (consultant_id, status, notes, investment profile, income) are excluded.
ME_FIELDS = ["name", "corporate_name", "email", "phone", "whatsapp", "address", "occupation", "business", "family"]


async def _client_doc(user):
    if user["role"] != "client" or not user.get("client_id"):
        raise HTTPException(403, "Client profile only")
    doc = await db.clients.find_one({"id": user["client_id"], "tenant_id": user["tenant_id"]})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


def _view(doc):
    d = from_store("clients", dict(doc))
    out = {k: d.get(k) for k in ME_FIELDS}
    out["client_type"] = d.get("client_type")
    out["updated_at"] = d.get("updated_at")
    return out


@router.get("/profile")
async def get_profile(user=Depends(current)):
    return _view(await _client_doc(user))


@router.put("/profile")
async def update_profile(body: dict, request: Request, user=Depends(current)):
    before = await _client_doc(user)
    if before.get("status") == "terminated":
        raise HTTPException(403, "Your contract has ended. Your data is view-only.")
    data = {k: v for k, v in sanitize("clients", body).items() if k in ME_FIELDS}
    to_store("clients", data)
    data.update(updated_at=now_iso(), updated_by=user["id"], updated_by_role=user["role"])
    await db.clients.update_one({"id": before["id"]}, {"$set": data})
    after = await db.clients.find_one({"id": before["id"]})
    await audit(user, "update", "clients", before["id"], before=dict(before), after=dict(after), request=request)
    return _view(after)
