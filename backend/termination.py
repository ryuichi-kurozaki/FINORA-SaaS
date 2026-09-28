"""Contract termination by staff: legacy (pre-e-contract) contracts and ending the whole client relationship."""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import audit, client_user_ids, current, db, notify, now_iso, scope
from econtract import PRE_ACTIVE, _move
from sign_notify import send_ended_notice

router = APIRouter(prefix="/api")
_BG = set()
DONE = ["ENDED", "CANCELLED"]
LEGACY_FIELDS = ("id", "client_id", "name", "service_name", "fee_type", "fee", "status", "start_date", "end_date", "end_reason", "ended_at")


class TermIn(BaseModel):
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: str = Field(min_length=1, max_length=1000)


async def _client(user, cid):
    if user["role"] not in ("admin", "consultant"):
        raise HTTPException(403, "Forbidden")
    await scope(user, cid)
    cl = await db.clients.find_one({"id": cid, "tenant_id": user["tenant_id"]})
    if not cl:
        raise HTTPException(404, "Not found")
    return cl


async def _announce(user, cl, c, kind, link, label):
    uids = await client_user_ids(user["tenant_id"], cl["id"])
    await notify(user["tenant_id"], uids, "contract_ended" if kind == "contract" else "client_terminated", {"label": label}, cl["id"], link, user)
    t = await db.tenants.find_one({"id": user["tenant_id"]}, {"name": 1, "billing_profile": 1}) or {}
    issuer = (t.get("billing_profile") or {}).get("company_name") or t.get("name") or "FINORA"
    for uid in uids:
        task = asyncio.create_task(send_ended_notice(uid, c, kind, issuer, link))
        _BG.add(task)
        task.add_done_callback(_BG.discard)


async def _end_legacy(user, con, body, request):
    await db.contracts.update_one({"id": con["id"]}, {"$set": {"status": "ENDED", "end_date": body.end_date, "end_reason": body.reason, "auto_renew": False,
                                                                "ended_at": now_iso(), "ended_by": user["id"], "updated_at": now_iso()}})
    await audit(user, "terminate", "contracts", con["id"], before={"status": con["status"]},
                after={"status": "ENDED", "end_date": body.end_date, "reason": body.reason}, request=request, client_id=con["client_id"], label=con.get("name"))


async def _linked(tid):
    return [x for x in await db.econtracts.distinct("billing_contract_id", {"tenant_id": tid}) if x]


@router.get("/contracts/legacy")
async def legacy_contracts(client_id: Optional[str] = None, user=Depends(current)):
    q = await scope(user, client_id)
    rows = await db.contracts.find({**q, "id": {"$nin": await _linked(user["tenant_id"])}}).sort("created_at", -1).to_list(500)
    return [{k: r.get(k) for k in LEGACY_FIELDS} for r in rows]


@router.post("/contracts/{con_id}/terminate")
async def terminate_contract(con_id: str, body: TermIn, request: Request, user=Depends(current)):
    con = await db.contracts.find_one({"id": con_id, "tenant_id": user["tenant_id"]})
    if not con:
        raise HTTPException(404, "Not found")
    cl = await _client(user, con["client_id"])
    if con_id in await _linked(user["tenant_id"]):
        raise HTTPException(409, "This contract is managed by an e-contract. End it from the e-contract page.")
    if con["status"] in DONE:
        raise HTTPException(409, f"This step is not allowed in status {con['status']}")
    await _end_legacy(user, con, body, request)
    c = {"id": con_id, "tenant_id": user["tenant_id"], "number": con.get("name") or "", "service": con.get("service_name") or con.get("name") or "", "end_date": body.end_date}
    await _announce(user, cl, c, "contract", "/billing", con.get("name"))
    return {"status": "ENDED"}


@router.post("/clients/{cid}/terminate")
async def terminate_client(cid: str, body: TermIn, request: Request, user=Depends(current)):
    cl = await _client(user, cid)
    if cl.get("status") == "terminated":
        raise HTTPException(409, "This client is already terminated")
    ended = cancelled = 0
    for c in await db.econtracts.find({"client_id": cid, "tenant_id": user["tenant_id"], "contract_type": "CONSULTING", "status": {"$nin": DONE}}).to_list(500):
        if c["status"] in ("ACTIVE", "PAUSED"):
            await _move(c, ["ACTIVE", "PAUSED"], "ENDED", user, request, "end",
                        extra={"end_date": body.end_date, "end_reason": body.reason, "ended_at": now_iso(), "ended_by": user["id"], "ended_by_name": user.get("name")})
            if c.get("billing_contract_id"):
                await db.contracts.update_one({"id": c["billing_contract_id"]}, {"$set": {"status": "ENDED", "end_date": body.end_date, "updated_at": now_iso()}})
            ended += 1
        elif c["status"] in PRE_ACTIVE + ["BOTH_SIGNED"]:
            await _move(c, PRE_ACTIVE + ["BOTH_SIGNED"], "CANCELLED", user, request, "cancel", extra={"cancel_reason": body.reason})
            cancelled += 1
    for con in await db.contracts.find({"client_id": cid, "tenant_id": user["tenant_id"], "status": {"$nin": DONE}}).to_list(500):
        await _end_legacy(user, con, body, request)
        ended += 1
    await db.clients.update_one({"id": cid}, {"$set": {"status": "terminated", "terminated_at": now_iso(), "terminated_end_date": body.end_date,
                                                       "terminated_reason": body.reason, "terminated_by": user["id"], "updated_at": now_iso()}})
    await audit(user, "terminate", "clients", cid, before={"status": cl.get("status")},
                after={"status": "terminated", "end_date": body.end_date, "reason": body.reason, "contracts_ended": ended, "contracts_cancelled": cancelled},
                request=request, client_id=cid, label=cl.get("corporate_name") or cl.get("name"))
    await _announce(user, cl, {"id": cid, "tenant_id": user["tenant_id"], "end_date": body.end_date}, "client", "/dashboard", cl.get("corporate_name") or cl.get("name"))
    return {"status": "terminated", "ended": ended, "cancelled": cancelled}
