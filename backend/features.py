import io
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import (db, new_id, now_iso, clean, current, staff, admin_only, scope, audit, ip_of, notify, notify_other_side,
                  client_user_ids, consultant_ids)
from analytics import load, summarize, build_breakdowns, get_fx
from calc import merge_history

router = APIRouter(prefix="/api")
CORR_TARGETS = ("assets", "accounts", "liabilities", "transactions", "cashflows", "portfolio", "documents", "goals")
REQ_STATUS = ("new", "accepted", "reviewing", "meeting_scheduled", "in_progress", "completed", "closed")
CONSENT_DOCS = {"terms": "2026.1", "privacy": "2026.1", "personal_info": "2026.1"}


async def _get(coll, user, item_id):
    d = await db[coll].find_one({"$and": [await scope(user), {"id": item_id}]})
    if not d:
        raise HTTPException(404, "Not found")
    return d


# ---- Net-worth history & saved snapshots ----
@router.get("/history")
async def history(client_id: Optional[str] = None, user=Depends(current)):
    q = await scope(user, client_id)
    monthly = await db.snapshots.find(q, {"_id": 0}).to_list(50000)
    agg = {}
    for s in monthly:
        x = agg.setdefault(s["date"], {"date": s["date"], "total_assets": 0, "total_liabilities": 0, "net_worth": 0})
        for k in ("total_assets", "total_liabilities", "net_worth"):
            x[k] += s.get(k) or 0
    daily = await db.daily_snapshots.find(q, {"_id": 0}).to_list(50000)
    return merge_history(sorted(agg.values(), key=lambda x: x["date"]), daily)


class SnapIn(BaseModel):
    client_id: str
    label: Optional[str] = Field(None, max_length=120)


@router.post("/snapshots")
async def save_snapshot(body: SnapIn, request: Request, user=Depends(current)):
    await scope(user, body.client_id)
    data = await load(user, body.client_id)
    s = summarize(data["assets"], data["liabilities"])
    b = build_breakdowns(data)
    s2 = await db.settings.find_one({"tenant_id": user["tenant_id"]}) or {}
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], "client_id": body.client_id, "label": body.label or "",
           "date": now_iso()[:10], "base_currency": s2.get("base_currency", "JPY"), "fx": await get_fx(user["tenant_id"]),
           "fx_date": s2.get("fx_updated_at"), "totals": {k: round(s[k]) for k in ("total_assets", "total_liabilities", "net_worth", "invested_value", "unrealized_pl")},
           "by_asset_class": b["asset_class"], "by_currency": b["currency"], "by_account": b["institution"],
           "assets": [{"id": a["id"], "name": a.get("name"), "asset_class": a.get("asset_class"), "currency": a.get("currency"),
                       "value_local": a.get("current_value"), "value_base": round(a.get("value_jpy") or 0)} for a in data["assets"]],
           "created_by": user["id"], "created_by_name": user.get("name"), "created_by_role": user["role"], "created_at": now_iso()}
    await db.saved_snapshots.insert_one(doc)
    await audit(user, "create", "saved_snapshots", doc["id"], after={"label": doc["label"], "totals": doc["totals"]}, request=request, client_id=body.client_id)
    return clean(doc)


@router.get("/snapshots")
async def list_snapshots(client_id: Optional[str] = None, user=Depends(current)):
    return [clean(x) for x in await db.saved_snapshots.find(await scope(user, client_id), {"assets": 0}).sort("created_at", -1).to_list(500)]


@router.get("/snapshots/{sid}")
async def get_snapshot(sid: str, user=Depends(current)):
    return clean(await _get("saved_snapshots", user, sid))


# ---- Correction requests (consultant -> client) ----
class CorrectionIn(BaseModel):
    client_id: str
    target_entity: str
    target_id: Optional[str] = None
    target_label: Optional[str] = Field(None, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)
    requested_change: str = Field(min_length=1, max_length=2000)
    comment: Optional[str] = Field("", max_length=2000)
    due_date: Optional[str] = None


class NoteIn(BaseModel):
    note: Optional[str] = Field("", max_length=2000)


@router.post("/corrections")
async def create_correction(body: CorrectionIn, request: Request, user=Depends(staff)):
    await scope(user, body.client_id)
    if body.target_entity not in CORR_TARGETS:
        raise HTTPException(422, "Invalid target")
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], **body.model_dump(), "status": "open", "created_by": user["id"],
           "created_by_name": user.get("name"), "created_at": now_iso(), "updated_at": now_iso()}
    await db.corrections.insert_one(doc)
    await audit(user, "consultant_request", "corrections", doc["id"], after=clean(dict(doc)), request=request)
    await notify(user["tenant_id"], await client_user_ids(user["tenant_id"], body.client_id), "correction_requested",
                 {"label": body.target_label or body.target_entity}, body.client_id, "/consulting?tab=corrections", user)
    return clean(doc)


@router.get("/corrections")
async def list_corrections(client_id: Optional[str] = None, status: Optional[str] = None, user=Depends(current)):
    q = await scope(user, client_id)
    if status:
        q["status"] = status
    return [clean(x) for x in await db.corrections.find(q).sort("created_at", -1).to_list(1000)]


@router.put("/corrections/{cid}/resolve")
async def resolve_correction(cid: str, body: NoteIn, request: Request, user=Depends(current)):
    if user["role"] != "client":
        raise HTTPException(403, "Only the client can mark a correction as fixed")
    d = await _get("corrections", user, cid)
    upd = {"status": "resolved", "resolution_note": body.note, "resolved_at": now_iso(), "updated_at": now_iso()}
    await db.corrections.update_one({"id": cid}, {"$set": upd})
    await audit(user, "update", "corrections", cid, before={"status": d["status"]}, after=upd, request=request, client_id=d["client_id"], label=d.get("target_label"))
    await notify(user["tenant_id"], [d["created_by"]], "correction_resolved", {"label": d.get("target_label") or d["target_entity"]},
                 d["client_id"], f"/clients/{d['client_id']}", user)
    return {"ok": True}


@router.put("/corrections/{cid}/close")
async def close_correction(cid: str, request: Request, user=Depends(staff)):
    d = await _get("corrections", user, cid)
    await db.corrections.update_one({"id": cid}, {"$set": {"status": "closed", "updated_at": now_iso()}})
    await audit(user, "update", "corrections", cid, before={"status": d["status"]}, after={"status": "closed"}, request=request, client_id=d["client_id"], label=d.get("target_label"))
    return {"ok": True}


# ---- Consulting requests (client -> consultant) ----
class RequestIn(BaseModel):
    category: str = Field(max_length=60)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    asset_id: Optional[str] = None
    preferred_at: Optional[str] = None
    doc_id: Optional[str] = None
    notes: Optional[str] = Field("", max_length=2000)


class ManageIn(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    answer: Optional[str] = Field(None, max_length=5000)
    meeting_at: Optional[str] = None


@router.post("/requests")
async def create_request(body: RequestIn, request: Request, user=Depends(current)):
    if user["role"] != "client":
        raise HTTPException(403, "Only clients can create consulting requests")
    cid = user["client_id"]
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], "client_id": cid, **body.model_dump(), "status": "new",
           "assignee_id": (await consultant_ids(user["tenant_id"], cid) or [None])[0], "created_by": user["id"],
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.requests.insert_one(doc)
    await audit(user, "create", "requests", doc["id"], after=clean(dict(doc)), request=request)
    await notify_other_side(user, cid, "request_new", {"label": body.title}, "/consulting?tab=requests")
    return clean(doc)


@router.get("/requests")
async def list_requests(client_id: Optional[str] = None, user=Depends(current)):
    return [clean(x) for x in await db.requests.find(await scope(user, client_id)).sort("created_at", -1).to_list(1000)]


@router.put("/requests/{rid}/manage")
async def manage_request(rid: str, body: ManageIn, request: Request, user=Depends(staff)):
    d = await _get("requests", user, rid)
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "status" in upd and upd["status"] not in REQ_STATUS:
        raise HTTPException(422, "Invalid status")
    if upd.get("meeting_at"):
        upd.setdefault("status", "meeting_scheduled")
        await db.tasks.insert_one({"id": new_id(), "tenant_id": user["tenant_id"], "client_id": d["client_id"], "kind": "meeting",
                                   "title": d["title"], "due_date": upd["meeting_at"][:10], "status": "open", "priority": "medium",
                                   "owner_id": user["id"], "owner_role": user["role"], "visibility": "shared", "created_at": now_iso()})
    upd["updated_at"] = now_iso()
    await db.requests.update_one({"id": rid}, {"$set": upd})
    await audit(user, "update", "requests", rid, before={k: d.get(k) for k in upd}, after=upd, request=request, client_id=d["client_id"], label=d["title"])
    await notify_other_side(user, d["client_id"], "request_updated", {"label": d["title"], "status": upd.get("status", d["status"])}, "/consulting?tab=requests")
    return {"ok": True}


# ---- Comments linked to records ----
class CommentIn(BaseModel):
    client_id: str
    target_type: str = Field(max_length=40)
    target_id: Optional[str] = None
    target_label: Optional[str] = Field(None, max_length=200)
    body: str = Field(min_length=1, max_length=3000)


@router.get("/comments")
async def list_comments(client_id: str, target_type: Optional[str] = None, target_id: Optional[str] = None, user=Depends(current)):
    q = await scope(user, client_id)
    if target_type:
        q["target_type"] = target_type
    if target_id:
        q["target_id"] = target_id
    return [clean(x) for x in await db.comments.find(q).sort("created_at", 1).to_list(1000)]


@router.post("/comments")
async def add_comment(body: CommentIn, request: Request, user=Depends(current)):
    await scope(user, body.client_id)
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], **body.model_dump(), "author_id": user["id"],
           "author_name": user.get("name"), "author_role": user["role"], "created_at": now_iso()}
    await db.comments.insert_one(doc)
    await audit(user, "create", "comments", doc["id"], after=clean(dict(doc)), request=request)
    await notify_other_side(user, body.client_id, "comment_new", {"label": body.target_label or body.target_type}, f"/timeline")
    return clean(doc)


# ---- Notifications ----
@router.get("/notifications")
async def list_notifications(user=Depends(current)):
    items = [clean(x) for x in await db.notifications.find({"user_id": user["id"]}).sort("created_at", -1).to_list(200)]
    return {"items": items, "unread": sum(not x["read"] for x in items)}


@router.post("/notifications/read-all")
async def read_all(user=Depends(current)):
    await db.notifications.update_many({"user_id": user["id"], "read": False}, {"$set": {"read": True}})
    return {"ok": True}


@router.post("/notifications/{nid}/read")
async def read_one(nid: str, user=Depends(current)):
    await db.notifications.update_one({"id": nid, "user_id": user["id"]}, {"$set": {"read": True}})
    return {"ok": True}


# ---- Timeline (derived from audit log + records; no duplicate storage) ----
@router.get("/timeline")
async def timeline(client_id: str, user=Depends(current)):
    q = await scope(user, client_id)
    logs = await db.audit_logs.find({"tenant_id": user["tenant_id"], "client_id": client_id},
                                    {"_id": 0, "before": 0, "after": 0, "ip": 0}).sort("at", -1).to_list(300)
    events = [{"at": x["at"], "action": x["action"], "entity": x["entity"], "label": x.get("label"),
               "user_name": x.get("user_name") or x.get("user_email"), "user_role": x.get("user_role")} for x in logs]
    for c in await db.consulting.find({**q, "kind": "meeting"}, {"_id": 0, "date": 1, "title": 1}).to_list(200):
        events.append({"at": c["date"], "action": "MEETING", "entity": "consulting", "label": c["title"]})
    cl = await db.clients.find_one({"tenant_id": user["tenant_id"], "id": client_id}, {"_id": 0, "created_at": 1})
    if cl:
        events.append({"at": cl["created_at"], "action": "REGISTERED", "entity": "clients", "label": None})
    return sorted(events, key=lambda e: e["at"] or "", reverse=True)


# ---- Consents ----
class ConsentIn(BaseModel):
    docs: list[str]


@router.get("/consents/status")
async def consent_status(user=Depends(current)):
    hist = [clean(x) for x in await db.consents.find({"user_id": user["id"]}).sort("agreed_at", -1).to_list(200)]
    have = {(h["doc"], h["version"]) for h in hist}
    pending = [{"doc": k, "version": v} for k, v in CONSENT_DOCS.items() if (k, v) not in have]
    return {"required": pending if user["role"] == "client" else [], "pending": pending, "history": hist, "current": CONSENT_DOCS}


@router.post("/consents")
async def agree(body: ConsentIn, request: Request, user=Depends(current)):
    docs = [d for d in body.docs if d in CONSENT_DOCS]
    for d in docs:
        await db.consents.insert_one({"id": new_id(), "tenant_id": user["tenant_id"], "user_id": user["id"], "doc": d,
                                      "version": CONSENT_DOCS[d], "agreed_at": now_iso(), "ip": ip_of(request),
                                      "ua": request.headers.get("user-agent", "")[:300]})
    await audit(user, "consent", "consents", user["id"], after={d: CONSENT_DOCS[d] for d in docs}, request=request,
                client_id=user.get("client_id"))
    return {"ok": True}


# ---- Report generation log & backup ----
class ReportLogIn(BaseModel):
    client_id: Optional[str] = None
    report_type: str = Field(max_length=60)


@router.post("/reports/log")
async def report_log(body: ReportLogIn, request: Request, user=Depends(current)):
    if body.client_id:
        await scope(user, body.client_id)
    await audit(user, "export", "reports", None, after={"type": body.report_type, "format": "pdf"}, request=request,
                client_id=body.client_id, label=body.report_type)
    return {"ok": True}


BACKUP_COLLS = ["clients", "accounts", "assets", "liabilities", "cashflows", "transactions", "goals", "consulting", "tasks",
                "documents", "corrections", "requests", "comments", "snapshots", "saved_snapshots", "settings", "consents"]


@router.get("/admin/backup")
async def backup(request: Request, user=Depends(admin_only)):
    out = {"tenant_id": user["tenant_id"], "generated_at": now_iso(), "note": "Encrypted fields remain encrypted."}
    for c in BACKUP_COLLS:
        out[c] = [clean(x) for x in await db[c].find({"tenant_id": user["tenant_id"]}).to_list(100000)]
    await audit(user, "export", "backup", user["tenant_id"], after={k: len(out[k]) for k in BACKUP_COLLS}, request=request)
    buf = io.BytesIO(json.dumps(out, ensure_ascii=False, default=str).encode())
    return StreamingResponse(buf, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="finora_backup.json"'})
