import io
import csv
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

import pricing
import txlink
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


CUR_MAP = {"円": "JPY", "-": "JPY", "": "JPY", "米ドル": "USD", "ドル": "USD", "ユーロ": "EUR"}


def _rk_decode(raw):
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def _rk_balance(rows, header):
    """楽天証券 保有残高(assetbalance) → holdings."""
    c = {"name": _rk_col(header, "ファンド"), "qty": _rk_col(header, "保有数量"), "acq": _rk_col(header, "平均取得価額"),
         "nav": _rk_col(header, "基準価額"), "cur": _rk_col(header, "通貨単位"), "acct": _rk_col(header, "口座区分")}

    def g(r, k):
        j = c.get(k)
        return r[j].strip() if j is not None and j < len(r) else ""

    out = []
    for r in rows[1:]:
        if not any(x.strip() for x in r):
            continue
        name, qty = g(r, "name"), _rk_num(g(r, "qty"))
        if not name or qty <= 0:
            continue
        acct = g(r, "acct")
        out.append({"asset_class": "fund", "name": name[:200], "currency": CUR_MAP.get(g(r, "cur"), "JPY"),
                    "acquisition_price": _rk_num(g(r, "acq")), "quantity": round(qty, 4),
                    "current_price": _rk_num(g(r, "nav")) or _rk_num(g(r, "acq")), "price_unit": 10000,
                    "notes": "楽天証券インポート" + (f"・{acct}口座" if acct and acct != "-" else "")})
    return out


def _rk_history(rows, header):
    """楽天証券 取引履歴(tradehistory) → aggregate net holdings per fund."""
    c = {"name": _rk_col(header, "ファンド名"), "qty": _rk_col(header, "数量"), "amount": _rk_col(header, "受渡金額"),
         "price": _rk_col(header, "単価"), "tx": _rk_col(header, "取引"), "date": _rk_col(header, "約定日"),
         "cur": _rk_col(header, "決済通貨", "通貨")}

    def g(r, k):
        j = c.get(k)
        return r[j].strip() if j is not None and j < len(r) else ""

    funds = {}
    for r in rows[1:]:
        if not any(x.strip() for x in r):
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
    out = []
    for name, f in funds.items():
        if round(f["qty"], 4) <= 0:
            continue
        acq = round(f["cost"] / f["qty"] * 10000, 2) if f["qty"] else 0.0
        out.append({"asset_class": "fund", "name": name[:200], "currency": CUR_MAP.get(f["cur"], "JPY"),
                    "acquired_date": f["first"], "acquisition_price": acq, "quantity": round(f["qty"], 4),
                    "current_price": f["last_price"] or acq, "price_unit": 10000, "notes": "楽天証券インポート"})
    return out


def _rk_tx(rows, header):
    """楽天証券 取引履歴(tradehistory) → individual transaction rows."""
    c = {"name": _rk_col(header, "ファンド名"), "qty": _rk_col(header, "数量"), "amount": _rk_col(header, "受渡金額"),
         "price": _rk_col(header, "単価"), "tx": _rk_col(header, "取引"), "date": _rk_col(header, "約定日"),
         "fee": _rk_col(header, "経費"), "cur": _rk_col(header, "決済通貨", "通貨")}

    def g(r, k):
        j = c.get(k)
        return r[j].strip() if j is not None and j < len(r) else ""

    out = []
    for r in rows[1:]:
        if not any(x.strip() for x in r):
            continue
        name = g(r, "name")
        if not name:
            continue
        tx_type = "sell" if "売" in g(r, "tx") else "buy"
        out.append({"date": _rk_date(g(r, "date")), "tx_type": tx_type, "quantity": round(_rk_num(g(r, "qty")), 4),
                    "unit_price": _rk_num(g(r, "price")), "amount": _rk_num(g(r, "amount")), "fee": _rk_num(g(r, "fee")),
                    "currency": CUR_MAP.get(g(r, "cur"), "JPY"), "notes": name[:200]})
    return out


def rakuten_format(raw: bytes):
    """Return 'balance' | 'history' | None for a Rakuten fund CSV, by header."""
    text = _rk_decode(raw)
    if not text:
        return None
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return None
    h = [x.strip() for x in rows[0]]
    if _rk_col(h, "保有数量") is not None and _rk_col(h, "基準価額") is not None:
        return "balance"
    if _rk_col(h, "ファンド名") is not None and _rk_col(h, "約定日") is not None:
        return "history"
    return None


def parse_rakuten_funds(raw: bytes):
    """Detect and parse a Rakuten Securities mutual-fund CSV (Shift-JIS): asset balance (保有残高)
    or trade history (取引履歴). Returns a list of holding dicts, or None if not a Rakuten fund CSV."""
    text = _rk_decode(raw)
    if not text:
        return None
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return None
    header = [h.strip() for h in rows[0]]
    if _rk_col(header, "保有数量") is not None and _rk_col(header, "基準価額") is not None:
        return _rk_balance(rows, header)
    if _rk_col(header, "ファンド名") is not None and _rk_col(header, "約定日") is not None:
        return _rk_history(rows, header)
    return None


OKASAN_TX = [("買付", "buy"), ("買", "buy"), ("売却", "sell"), ("売付", "sell"), ("売", "sell"),
             ("分配金", "dividend"), ("配当", "dividend"), ("利金", "interest"), ("利息", "interest"),
             ("出金", "withdrawal"), ("入金", "deposit_tx"), ("振替", "transfer")]


def _okasan_decode(raw):
    for enc in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def _okasan_tx_type(s):
    for key, val in OKASAN_TX:
        if key in s:
            return val
    return "other"


def parse_okasan(raw: bytes):
    """岡三証券 取引履歴CSV (UTF-8 BOM; header row is not the first line). Returns transaction dicts, or None."""
    text = _okasan_decode(raw)
    if not text:
        return None
    rows = list(csv.reader(text.splitlines()))
    hi = None
    for i, r in enumerate(rows):
        if "約定日" in r and "銘柄名" in r and "取引区分" in r:
            hi = i
            break
    if hi is None:
        return None
    header = [h.strip() for h in rows[hi]]
    c = {"date": _rk_col(header, "約定日"), "name": _rk_col(header, "銘柄名"), "memo": _rk_col(header, "摘要"),
         "prod": _rk_col(header, "商品"), "tx": _rk_col(header, "取引区分"), "qty": _rk_col(header, "数量"),
         "price": _rk_col(header, "単価"), "amount": _rk_col(header, "受渡金額", "決済損益"), "fee": _rk_col(header, "手数料"),
         "rate": _rk_col(header, "レート"), "cur": _rk_col(header, "決済通貨"), "cur2": _rk_col(header, "発行通貨")}

    def g(r, k):
        j = c.get(k)
        return r[j].strip() if j is not None and j < len(r) else ""

    out = []
    for r in rows[hi + 1:]:
        if not any(x.strip() for x in r):
            continue
        tx = g(r, "tx")
        if not tx:
            continue
        name = g(r, "name") or g(r, "memo") or g(r, "prod")
        cur = g(r, "cur") or g(r, "cur2")
        out.append({"date": _rk_date(g(r, "date")), "tx_type": _okasan_tx_type(tx),
                    "quantity": round(_rk_num(g(r, "qty")), 4), "unit_price": _rk_num(g(r, "price")),
                    "amount": _rk_num(g(r, "amount")), "fee": _rk_num(g(r, "fee")), "fx_rate": _rk_num(g(r, "rate")),
                    "currency": CUR_MAP.get(cur, "JPY"), "notes": (f"{name}／{tx}"[:200] if name else tx[:200])})
    return out


def parse_okasan_holdings(raw: bytes):
    """岡三証券 預り資産(保有残高)CSV → holdings. Header row is not the first line. Returns list, or None."""
    text = _okasan_decode(raw)
    if not text:
        return None
    rows = list(csv.reader(text.splitlines()))
    hi = None
    for i, r in enumerate(rows):
        if "銘柄名" in r and "保有数量" in r and _rk_col(r, "取得コスト", "個別元本") is not None:
            hi = i
            break
    if hi is None:
        return None
    header = [h.strip() for h in rows[hi]]
    c = {"name": _rk_col(header, "銘柄名"), "acct": _rk_col(header, "預り区分"), "qty": _rk_col(header, "保有数量"),
         "acq": _rk_col(header, "取得コスト", "個別元本"), "price": _rk_col(header, "参考時価"),
         "date": _rk_col(header, "基準日"), "cur": _rk_col(header, "通貨")}

    def g(r, k):
        j = c.get(k)
        return r[j].strip() if j is not None and j < len(r) else ""

    out = []
    for r in rows[hi + 1:]:
        if not any(x.strip() for x in r):
            continue
        name, qty = g(r, "name"), _rk_num(g(r, "qty"))
        if not name or qty <= 0:
            continue
        acct = g(r, "acct")
        out.append({"asset_class": "fund", "name": name[:200], "currency": CUR_MAP.get(g(r, "cur"), "JPY"),
                    "acquisition_price": _rk_num(g(r, "acq")), "quantity": round(qty, 4),
                    "current_price": _rk_num(g(r, "price")) or _rk_num(g(r, "acq")), "price_unit": 10000,
                    "balance_date": _rk_date(g(r, "date")),
                    "notes": "岡三証券インポート" + (f"・{acct}口座" if acct and acct != "-" else "")})
    return out


async def _apply_asset(user, data, on_dup):
    """Insert or update one imported asset honoring on_dup ('create'|'update'|'skip'). Returns the action taken.
    A duplicate = same tenant+client+account and same ticker (if present) else same name."""
    if on_dup in ("update", "skip"):
        q = {"tenant_id": user["tenant_id"], "client_id": data.get("client_id")}
        acc = data.get("account_id")
        q["account_id"] = acc if acc else {"$in": [None, ""]}
        tk = (data.get("ticker") or "").strip()
        if tk:
            q["ticker"] = tk
        else:
            q["name"] = data.get("name")
        existing = await db["assets"].find_one(q)
        if existing:
            if on_dup == "skip":
                return "skipped"
            upd = to_store("assets", {**data, "updated_at": now_iso(), "updated_by": user["id"],
                                      "updated_by_role": user["role"], "source": "IMPORT"})
            await db["assets"].update_one({"id": existing["id"]}, {"$set": upd})
            return "updated"
    doc = to_store("assets", {"id": new_id(), "tenant_id": user["tenant_id"], **data, "created_at": now_iso(),
                              "updated_at": now_iso(), "created_by": user["id"], "updated_by": user["id"],
                              "updated_by_role": user["role"], "source": "IMPORT"})
    await db["assets"].insert_one(doc)
    return "created"


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
                      account_id: Optional[str] = Form(None), on_dup: Optional[str] = Form("create"), user=Depends(current)):
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
        fmt = rakuten_format(raw) if rk is not None else None
        if rk is None:
            ok = parse_okasan_holdings(raw)
            if ok is not None:
                rk, fmt = ok, "okasan_balance"
        if rk is not None:
            if not rk:
                raise HTTPException(422, "No open fund positions found in the file")
            if not client_id:
                raise HTTPException(422, "Select a client before importing")
            created = updated = skipped = 0
            errors = []
            tk_cache = {}
            for n, item in enumerate(rk, start=1):
                try:
                    data = sanitize("assets", item)
                    data["client_id"] = client_id
                    if account_id:
                        data["account_id"] = account_id
                    if not data.get("ticker") and data.get("asset_class") == "fund" and data.get("name"):
                        nm = data["name"]
                        if nm not in tk_cache:
                            tk_cache[nm] = await pricing.match_ticker(nm)
                        if tk_cache[nm]:
                            data["ticker"] = tk_cache[nm]
                            price, pdate = await pricing.fetch_price(tk_cache[nm], nm)
                            if price:
                                data["current_price"], data["price_date"] = round(price, 4), pdate
                    await check_write(user, "assets", data)
                    res = await _apply_asset(user, data, on_dup)
                    if res == "created":
                        created += 1
                    elif res == "updated":
                        updated += 1
                    else:
                        skipped += 1
                except HTTPException as e:
                    errors.append({"row": n, "error": e.detail})
                except Exception as e:
                    errors.append({"row": n, "error": str(e)[:200]})
            await audit(user, "import", "assets", None, after={"created": created, "updated": updated, "skipped": skipped, "errors": len(errors), "file": file.filename, "format": fmt or "rakuten"}, request=request)
            return {"created": created, "updated": updated, "skipped": skipped, "errors": errors[:50], "format": fmt}
    if entity == "transactions":
        txs = fmt = None
        if rakuten_format(raw) == "history":
            text = _rk_decode(raw)
            csv_rows = list(csv.reader(text.splitlines()))
            txs, fmt = _rk_tx(csv_rows, [h.strip() for h in csv_rows[0]]), "history"
        else:
            ok = parse_okasan(raw)
            if ok is not None:
                txs, fmt = ok, "okasan"
        if txs is not None:
            if not client_id:
                raise HTTPException(422, "Select a client before importing")
            if not txs:
                raise HTTPException(422, "No transactions found in the file")
            created = 0
            errors = []
            for n, item in enumerate(txs, start=1):
                try:
                    data = sanitize("transactions", item)
                    data["client_id"] = client_id
                    if account_id:
                        data["account_id"] = account_id
                    await check_write(user, "transactions", data)
                    doc = to_store("transactions", {"id": new_id(), "tenant_id": user["tenant_id"], **data, "created_at": now_iso(),
                                                    "updated_at": now_iso(), "created_by": user["id"], "updated_by": user["id"],
                                                    "updated_by_role": user["role"], "source": "IMPORT"})
                    await db["transactions"].insert_one(doc)
                    created += 1
                except HTTPException as e:
                    errors.append({"row": n, "error": e.detail})
                except Exception as e:
                    errors.append({"row": n, "error": str(e)[:200]})
            await audit(user, "import", "transactions", None, after={"created": created, "errors": len(errors), "file": file.filename, "format": fmt}, request=request)
            link = await txlink.rebuild(user["tenant_id"], client_id)
            return {"created": created, "updated": 0, "skipped": 0, "errors": errors[:50], "format": fmt, "link": link}
    try:
        df = pd.read_excel(io.BytesIO(raw)) if file.filename.lower().endswith((".xlsx", ".xls")) else pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise HTTPException(422, "Could not parse file")
    df = df.where(pd.notnull(df), None)
    created = updated = skipped = 0
    errors = []
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
            if entity == "assets":
                res = await _apply_asset(user, data, on_dup)
                if res == "created":
                    created += 1
                elif res == "updated":
                    updated += 1
                else:
                    skipped += 1
            else:
                doc = to_store(entity, {"id": new_id(), "tenant_id": user["tenant_id"], **data, "created_at": now_iso(),
                                        "updated_at": now_iso(), "created_by": user["id"], "updated_by": user["id"],
                                        "updated_by_role": user["role"], "source": "IMPORT" if entity in OWNED else None})
                await db[entity].insert_one(doc)
                created += 1
        except HTTPException as e:
            errors.append({"row": n, "error": e.detail})
        except Exception as e:
            errors.append({"row": n, "error": str(e)[:200]})
    await audit(user, "import", entity, None, after={"created": created, "updated": updated, "skipped": skipped, "errors": len(errors), "file": file.filename}, request=request)
    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors[:50]}


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
