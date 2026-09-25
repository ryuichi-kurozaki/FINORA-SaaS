import re
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, now, now_iso, new_id, clean, ip_of, admin_only, audit

router = APIRouter(prefix="/api")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TYPES = ("individual", "corporate", "consulting_firm", "other")
STATUSES = ("new", "in_progress", "done")


class InquiryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=150)
    email: str = Field(max_length=200)
    phone: Optional[str] = Field(None, max_length=40)
    inquiry_type: str = "other"
    message: str = Field(min_length=5, max_length=3000)
    lang: str = "ja"
    website: Optional[str] = None  # honeypot


class StatusIn(BaseModel):
    status: str


@router.post("/public/inquiries")
async def create_inquiry(body: InquiryIn, request: Request):
    if body.website:
        return {"ok": True}
    if not EMAIL_RE.match(body.email.strip()):
        raise HTTPException(422, "Invalid email address")
    if body.inquiry_type not in TYPES:
        raise HTTPException(422, "Invalid inquiry type")
    ip = ip_of(request)
    since = (now() - timedelta(hours=1)).isoformat()
    if await db.inquiries.count_documents({"ip": ip, "created_at": {"$gt": since}}) >= 5:
        raise HTTPException(429, "Too many submissions. Please try again later.")
    tenant = await db.tenants.find_one({}, sort=[("created_at", 1)])
    doc = {"id": new_id(), "tenant_id": tenant["id"], **body.model_dump(exclude={"website"}),
           "email": body.email.strip().lower(), "status": "new", "ip": ip, "created_at": now_iso()}
    await db.inquiries.insert_one(doc)
    return {"ok": True}


@router.get("/inquiries")
async def list_inquiries(user=Depends(admin_only)):
    return [clean(i) for i in await db.inquiries.find({"tenant_id": user["tenant_id"]}).sort("created_at", -1).to_list(1000)]


@router.put("/inquiries/{iid}")
async def update_inquiry(iid: str, body: StatusIn, request: Request, user=Depends(admin_only)):
    if body.status not in STATUSES:
        raise HTTPException(422, "Invalid status")
    before = await db.inquiries.find_one({"id": iid, "tenant_id": user["tenant_id"]})
    if not before:
        raise HTTPException(404, "Not found")
    await db.inquiries.update_one({"id": iid}, {"$set": {"status": body.status}})
    await audit(user, "update", "inquiries", iid, before={"status": before["status"]}, after={"status": body.status}, request=request)
    return {"ok": True}
