import logging
import os
import re
from datetime import timedelta
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, now, now_iso, new_id, clean, ip_of, admin_only, audit
from email_service import send_email

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
    try:
        rows = "".join(f"<tr><td style='padding:4px 12px 4px 0;color:#64748b'>{escape(k)}</td><td>{escape(str(v or '—'))}</td></tr>"
                       for k, v in (("Name", body.name), ("Company", body.company), ("Email", doc["email"]), ("Phone", body.phone), ("Type", body.inquiry_type), ("Lang", body.lang)))
        await send_email(to=os.environ["SITE_INQUIRY_EMAIL"], subject=f"【FINORA】お問い合わせ: {body.name}",
                         html=f"<table>{rows}</table><p style='white-space:pre-line'>{escape(body.message)}</p>", kind="inquiry")
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).error("inquiry mail failed: %s", e)
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
