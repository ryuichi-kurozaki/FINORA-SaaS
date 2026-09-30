import io
import csv
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from core import forbid_demo, db, new_id, now_iso, clean, current, scope, audit, notify_other_side
from crud import ENTITIES, OWNED, sanitize, to_store, list_items, check_write

router = APIRouter(prefix="/api")
bucket = AsyncIOMotorGridFSBucket(db, bucket_name="documents")
MAX_FILE = 15 * 1024 * 1024
DOC_TYPES = ("application/pdf", "image/", "text/", "application/vnd", "application/msword", "application/zip")


def _rk_num(s):
    s = str(s or "").replace(",", "").replace("円", "").strip()
    if s in ("", "-", "‐"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _rk_date(s):
    s = (s or "").strip()
    for f in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    return None


def _rk_col(header, *subs):
    for n, h in enumerate(header):
        if any(s in h for s in subs):
            return n
    return None


def parse_rakuten_funds(raw: bytes):
    """Detect and aggregate a Rakuten Securities mutual-fund trade-history CSV (Shift-JIS).
    Returns a list of holding dicts (net position per fund) or None if not this format."""
    text = None
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        return None
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return None
    header = [h.strip() for h in rows[0]]
    if _rk_col(header, "ファンド名") is None or _rk_col(header, "約定日") is None:
        return None
    ci = {"name": _rk_col(header, "ファンド名"), "qty": _rk_col(header, "数量"), "amount": _rk_col(header, "受渡金額"),
          "price": _rk_col(header, "単価"), "tx": _rk_col(header, "取引"), "date": _rk_col(header, "約定日"),
          "cur": _rk_col(header, "決済通貨", "通貨")}

    def g(r, key):
        j = ci.get(key)
        return r[j].strip() if j is not None and j < len(r) else ""

    funds = {}
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        name = g(r, "name")
        if not name:
            continue
        qty, amount, price = _rk_num(g(r, "qty")), _rk_num(g(r, "amount")), _rk_num(g(r, "price"))
        sign = -1 if ("売" in g(r, "tx")) else 1
        date = _rk_date(g(r, "date"))
        f = funds.setdefault(name, {"qty": 0.0, "cost": 0.0, "first": None, "last_price": 0.0, "cur": g(r, "cur") or "円"})
        f["qty"] += sign * qty
        f["cost"] += sign * amount
        if price:
            f["last_price"] = price
        if sign > 0 and date and (f["first"] is None or date < f["first"]):
            f["first"] = date
    cur_map = {"円": "JPY", "米ドル": "USD", "ドル": "USD"}
    out = []
    for name, f in funds.items():
        if round(f["qty"], 4) <= 0:
            continue
        acq = round(f["cost"] / f["qty"] * 10000, 2) if f["qty"] else 0.0
        out.append({"asset_class": "fund", "name": name[:200], "currency": cur_map.get(f["cur"], "JPY"),
                    "acquired_date": f["first"], "acquisition_price": acq, "quantity": round(f["qty"], 4),
                    "current_price": f["last_price"] or acq, "price_unit": 10000, "notes": "楽天証券インポート"})
    return out


@router.get("/io/export/{entity}")
async def export(entity: str, request: Request, fmt: str = "csv", client_id: Optional[str] = None, user=Depends(current)):
    if entity not in ENTITIES:
        raise HTTPException(404, "Unknown entity")
    if user["role"] == "consultant":
        raise HTTPException(403, "Forbidden")
    items = await list_items(user, entity, client_id)
    cols = ["id"] + ENTITIES[entity]["fields"]
    df = pd.DataFrame([{c: i.get(c) for c in cols} for i in items], columns=cols)
    buf = io.BytesIO()
    if fmt == "xlsx":
        df.to_excel(buf, index=False)
        mime, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        buf.write(df.to_csv(index=False).encode("utf-8-sig"))
        mime, ext = "text/csv", "csv"
    buf.seek(0)
    await audit(user, "export", entity, None, after={"count": len(items), "format": ext}, request=request)
    return StreamingResponse(buf, media_type=mime, headers={"Content-Disposition": f'attachment; filename="finora_{entity}.{ext}"'})


@router.post("/io/import/{entity}")
async def import_data(entity: str, request: Request, file: UploadFile = File(...), client_id: Optional[str] = Form(None),
                      account_id: Optional[str] = Form(None), user=Depends(current)):
    forbid_demo(user)
    if entity not in ENTITIES:
        raise HTTPException(404, "Unknown entity")
    if user["role"] == "client":
        client_id = user["client_id"]
    raw = await file.read()
    if len(raw) > MAX_FILE:
        raise HTTPException(413, "File too large")
    if entity == "assets":
        rk = parse_rakuten_funds(raw)
        if rk is not None:
            if not rk:
                raise HTTPException(422, "No open fund positions found in the Rakuten file")
            if not client_id:
                raise HTTPException(422, "Select a client before importing")
            created, errors = 0, []
            for n, item in enumerate(rk, start=1):
                try:
                    data = sanitize("assets", item)
                    data["client_id"] = client_id
                    if account_id:
                        data["account_id"] = account_id
                    await check_write(user, "assets", data)
                    doc = to_store("assets", {"id": new_id(), "tenant_id": user["tenant_id"], **data, "created_at": now_iso(),
                                              "updated_at": now_iso(), "created_by": user["id"], "updated_by": user["id"],
                                              "updated_by_role": user["role"], "source": "IMPORT"})
                    await db["assets"].insert_one(doc)
                    created += 1
                except HTTPException as e:
                    errors.append({"row": n, "error": e.detail})
                except Exception as e:
                    errors.append({"row": n, "error": str(e)[:200]})
            await audit(user, "import", "assets", None, after={"created": created, "errors": len(errors), "file": file.filename, "format": "rakuten"}, request=request)
            return {"created": created, "errors": errors[:50]}
    try:
        df = pd.read_excel(io.BytesIO(raw)) if file.filename.lower().endswith((".xlsx", ".xls")) else pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise HTTPException(422, "Could not parse file")
    df = df.where(pd.notnull(df), None)
    created, errors = 0, []
    for n, row in enumerate(df.to_dict("records"), start=2):
        try:
            data = sanitize(entity, {k: v for k, v in row.items() if v is not None})
            if client_id and entity != "clients":
                data["client_id"] = client_id
            if account_id and entity == "assets" and not data.get("account_id"):
                data["account_id"] = account_id
            if entity == "clients" and user["role"] == "consultant":
                data["consultant_id"] = user["id"]
            await check_write(user, entity, data)
            doc = to_store(entity, {"id": new_id(), "tenant_id": user["tenant_id"], **data, "created_at": now_iso(),
                                    "updated_at": now_iso(), "created_by": user["id"], "updated_by": user["id"],
                                    "updated_by_role": user["role"], "source": "IMPORT" if entity in OWNED else None})
            await db[entity].insert_one(doc)
            created += 1
        except HTTPException as e:
            errors.append({"row": n, "error": e.detail})
        except Exception as e:
            errors.append({"row": n, "error": str(e)[:200]})
    await audit(user, "import", entity, None, after={"created": created, "errors": len(errors), "file": file.filename}, request=request)
    return {"created": created, "errors": errors[:50]}


@router.get("/documents")
async def list_docs(client_id: Optional[str] = None, user=Depends(current)):
    q = await scope(user, client_id)
    return [clean(d) for d in await db.documents.find(q).sort("created_at", -1).to_list(2000)]


@router.post("/documents")
async def upload_doc(request: Request, file: UploadFile = File(...), client_id: str = Form(...), category: str = Form("other"),
                     notes: str = Form(""), fiscal_year: str = Form(""), institution: str = Form(""), asset_id: str = Form(""),
                     expiry_date: str = Form(""), user=Depends(current)):
    forbid_demo(user)
    if user["role"] != "client" or client_id != user.get("client_id"):
        raise HTTPException(403, "Only the client can upload their own documents")
    await scope(user, client_id)
    ctype = file.content_type or "application/octet-stream"
    if not ctype.startswith(DOC_TYPES):
        raise HTTPException(415, "Unsupported file type")
    raw = await file.read()
    if len(raw) > MAX_FILE:
        raise HTTPException(413, "File too large (max 15MB)")
    fid = await bucket.upload_from_stream(file.filename, raw, metadata={"tenant_id": user["tenant_id"], "content_type": ctype})
    doc = {"id": new_id(), "tenant_id": user["tenant_id"], "client_id": client_id, "category": category[:50],
           "filename": file.filename[:200], "content_type": ctype, "size": len(raw), "file_id": str(fid),
           "notes": notes[:1000], "fiscal_year": fiscal_year[:10], "institution": institution[:120], "asset_id": asset_id[:60] or None,
           "expiry_date": expiry_date[:10] or None, "uploaded_by": user["email"], "uploaded_by_role": user["role"], "created_at": now_iso()}
    await db.documents.insert_one(doc)
    await audit(user, "upload", "documents", doc["id"], after=clean(dict(doc)), request=request)
    await notify_other_side(user, client_id, "document_uploaded", {"label": doc["filename"]}, f"/clients/{client_id}")
    return clean(doc)


async def _doc(user, doc_id):
    q = await scope(user)
    d = await db.documents.find_one({"$and": [q, {"id": doc_id}]})
    if not d:
        raise HTTPException(404, "Not found")
    return d


@router.get("/documents/{doc_id}/download")
async def download_doc(doc_id: str, request: Request, user=Depends(current)):
    from bson import ObjectId
    d = await _doc(user, doc_id)
    stream = await bucket.open_download_stream(ObjectId(d["file_id"]))
    data = await stream.read()
    await audit(user, "download", "documents", doc_id, request=request)
    return StreamingResponse(io.BytesIO(data), media_type=d["content_type"],
                             headers={"Content-Disposition": f'attachment; filename="{d["id"]}"'})


@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str, request: Request, user=Depends(current)):
    from bson import ObjectId
    d = await _doc(user, doc_id)
    if user["role"] != "client":
        raise HTTPException(403, "Client documents cannot be deleted by staff")
    await bucket.delete(ObjectId(d["file_id"]))
    await db.documents.delete_one({"id": doc_id})
    await audit(user, "delete", "documents", doc_id, before=clean(dict(d)), request=request)
    return {"ok": True}
