"""Client-initiated contract requests: a client asks for a contract, a consultant approves it and the e-contract draft is created."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import audit, clean, current, db, new_id, notify, now_iso

router = APIRouter(prefix="/api/contract-requests")
logger = logging.getLogger(__name__)
STATUSES = ("PENDING", "APPROVED", "REJECTED", "WITHDRAWN")


class ReqIn(BaseModel):
    service_name: str = Field(min_length=1, max_length=120)
    note: str = Field("", max_length=2000)
    start_date: Optional[str] = None
    fee_type: str = "MONTHLY"
    lang: str = "ja"


class RejectIn(BaseModel):
    reason: str = Field("", max_length=500)


async def _staff_ids(tenant_id, client_id):
    q = {"tenant_id": tenant_id, "active": True, "role": {"$in": ["admin", "consultant"]}}
    return [u["id"] for u in await db.users.find(q, {"id": 1}).to_list(50)]


@router.post("")
async def create(body: ReqIn, request: Request, user=Depends(current)):
    if user["role"] != "client" or not user.get("client_id"):
        raise HTTPException(403, "Only clients can request a contract")
    if await db.contract_requests.find_one({"client_id": user["client_id"], "status": "PENDING"}):
        raise HTTPException(409, "You already have a contract request awaiting review")
    cl = await db.clients.find_one({"id": user["client_id"]}, {"name": 1, "corporate_name": 1}) or {}
    r = {"id": new_id(), "tenant_id": user["tenant_id"], "client_id": user["client_id"],
         "client_name": cl.get("corporate_name") or cl.get("name") or "", "service_name": body.service_name.strip(),
         "note": body.note.strip(), "start_date": body.start_date or None, "fee_type": body.fee_type,
         "lang": body.lang if body.lang in ("ja", "en", "pt") else "ja", "status": "PENDING",
         "requested_by": user["id"], "requested_by_name": user.get("name") or user["email"], "created_at": now_iso()}
    await db.contract_requests.insert_one(r)
    await notify(user["tenant_id"], await _staff_ids(user["tenant_id"], r["client_id"]), "contract_request_new",
                 {"label": f"{r['client_name']} / {r['service_name']}"}, r["client_id"], f"/clients/{r['client_id']}", user)
    await audit(user, "create", "contract_requests", r["id"], after=clean(dict(r)), request=request, client_id=r["client_id"], label=r["service_name"])
    return clean(r)


@router.get("")
async def listing(status: Optional[str] = None, client_id: Optional[str] = None, user=Depends(current)):
    q = {"tenant_id": user["tenant_id"]}
    if user["role"] == "client":
        q["client_id"] = user.get("client_id")
    elif client_id:
        q["client_id"] = client_id
    if status in STATUSES:
        q["status"] = status
    return [clean(r) for r in await db.contract_requests.find(q).sort("created_at", -1).to_list(300)]


async def _decide(rid, user, status, extra=None, request=None):
    r = await db.contract_requests.find_one({"id": rid, "tenant_id": user["tenant_id"]})
    if not r:
        raise HTTPException(404, "Not found")
    if r["status"] != "PENDING":
        raise HTTPException(409, f"This request is already {r['status']}")
    upd = {"status": status, "decided_by": user["id"], "decided_at": now_iso()} | (extra or {})
    await db.contract_requests.update_one({"id": rid}, {"$set": upd})
    await audit(user, status.lower(), "contract_requests", rid, before={"status": r["status"]}, after=upd, request=request,
                client_id=r["client_id"], label=r["service_name"])
    return r | upd


@router.post("/{rid}/reject")
async def reject(rid: str, body: RejectIn, request: Request, user=Depends(current)):
    if user["role"] == "client":
        raise HTTPException(403, "Forbidden")
    r = await _decide(rid, user, "REJECTED", {"reject_reason": body.reason.strip()}, request)
    await notify(r["tenant_id"], [r["requested_by"]], "contract_request_rejected", {"label": r["service_name"]}, r["client_id"], "/billing", user)
    return clean(r)


@router.post("/{rid}/withdraw")
async def withdraw(rid: str, request: Request, user=Depends(current)):
    r = await db.contract_requests.find_one({"id": rid, "tenant_id": user["tenant_id"]})
    if not r or (user["role"] == "client" and r["client_id"] != user.get("client_id")):
        raise HTTPException(404, "Not found")
    return clean(await _decide(rid, user, "WITHDRAWN", None, request))


async def mark_approved(rid, user, econtract):
    """Called by econtract creation when it fulfils a client request."""
    r = await _decide(rid, user, "APPROVED", {"econtract_id": econtract["id"], "econtract_number": econtract["number"]})
    await notify(r["tenant_id"], [r["requested_by"]], "contract_request_approved", {"label": f"{r['service_name']} / {econtract['number']}"},
                 r["client_id"], f"/econtracts/{econtract['id']}", user)
    return r
