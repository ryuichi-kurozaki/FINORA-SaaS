"""Two-tier e-contracts. FINORA_SAAS: FINORA (issuer) ⇄ consultant tenant owner (recipient).
CONSULTING: consultant (issuer) ⇄ client (recipient). Order (statement → confirm → agreement → recipient sign → issuer sign) is enforced here."""
import asyncio
import base64
import hashlib
import io
import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from core import (db, new_id, now_iso, clean, current, audit, notify, client_user_ids, scope, sees_all, require_service)
from econtract_tpl import DOC_TYPES, CYCLE, LANGS, T, build_sections, doc_title
from econtract_pdf import render
from io_routes import bucket
from billing import build_invoice, InvoiceIn
from tenancy import customer_fee
from sign_notify import KINDS, send_ended_notice, send_sign_request

_BG = set()

router = APIRouter(prefix="/api/econtracts")
PRE_ACTIVE = ["DRAFT", "IMPORTANT_INFO_SENT", "IMPORTANT_INFO_CONFIRMED", "CONTRACT_SENT", "FIRST_PARTY_SIGNED"]
PREFIX = {"FINORA_IMPORTANT_INFORMATION": "FIM", "FINORA_SERVICE_AGREEMENT": "FAG", "CONSULTING_IMPORTANT_INFORMATION": "CIM", "CONSULTING_AGREEMENT": "CAG"}
PARTY = {("FINORA_SAAS", "RECIPIENT"): ("コンサルタント", "Consultant", "Consultor"), ("FINORA_SAAS", "ISSUER"): ("FINORA運営", "FINORA", "FINORA"),
         ("CONSULTING", "RECIPIENT"): ("顧客", "Client", "Cliente"), ("CONSULTING", "ISSUER"): ("コンサルタント", "Consultant", "Consultor")}


class TermsIn(BaseModel):
    service_name: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    fee_type: str = Field("MONTHLY", pattern="^(MONTHLY|YEARLY|ONE_TIME|HOURLY)$")
    fee: float = Field(0, ge=0)
    tax_mode: str = Field("exclusive", pattern="^(exclusive|inclusive|exempt)$")
    tax_rate: float = Field(10, ge=0, le=100)
    start_date: str = Field(min_length=10, max_length=10)
    end_date: Optional[str] = None
    billing_day: int = Field(1, ge=1, le=28)
    payment_terms_days: int = Field(30, ge=0, le=120)
    auto_renew: bool = True
    plan_code: Optional[str] = None


class ECIn(BaseModel):
    contract_type: str = Field(pattern="^(FINORA_SAAS|CONSULTING)$")
    client_id: Optional[str] = None
    tenant_id: Optional[str] = None
    lang: str = Field("ja", pattern="^(ja|en|pt)$")
    terms: TermsIn
    fields: Dict[str, str] = {}


class SignIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    signature_png: str = Field(min_length=100, max_length=400_000)
    agree: bool


class EndIn(BaseModel):
    end_date: str = Field(min_length=10, max_length=10)
    reason: str = Field(min_length=1, max_length=1000)
    consultant_login: str = Field("read_only", pattern="^(read_only|blocked)$")
    client_access: str = Field("read_only", pattern="^(read_only|blocked)$")
    retention_days: int = Field(90, ge=0, le=3650)


def _ipua(request):
    if request is None:
        return "system", "system"
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (request.client.host if request.client else "")
    return ip, (request.headers.get("user-agent") or "")[:300]


def _fields(f):
    return {k: str(v)[:4000] for k, v in (f or {}).items() if k in T and str(v).strip()}


def is_issuer(user, c):
    if c["contract_type"] == "FINORA_SAAS":
        return bool(user.get("platform_admin"))
    return user["role"] in ("admin", "consultant") and user["tenant_id"] == c["tenant_id"] and (sees_all(user) or c.get("consultant_id") == user["id"])


def is_recipient(user, c):
    if c["contract_type"] == "FINORA_SAAS":
        return user["role"] == "admin" and user["tenant_id"] == c["tenant_id"]
    return user["role"] == "client" and user.get("client_id") == c.get("client_id")


async def load(user, cid):
    c = await db.econtracts.find_one({"id": cid})
    if c and c["contract_type"] == "FINORA_SAAS" and (user.get("platform_admin") or (c["tenant_id"] == user["tenant_id"] and user["role"] == "admin")):
        return c
    if c and c["contract_type"] == "CONSULTING" and c["tenant_id"] == user["tenant_id"]:
        if user["role"] == "client" and c["client_id"] == user.get("client_id") and c["status"] != "DRAFT":
            return c
        if user["role"] != "client":
            await scope(user, c["client_id"])
            return c
    raise HTTPException(404, "Not found")


async def _seq(owner, prefix):
    r = await db.counters.find_one_and_update({"tenant_id": owner, "key": f"ec-{prefix}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return f"{prefix}-{r['seq']:05d}"


REP = ("代表取締役 {n}", "Representative Director {n}", "Diretor Representante {n}")
CORP = ("法人番号：{n}", "Corporate No.: {n}", "Nº corporativo: {n}")


def _loc(v, lang):
    return (v.get(lang) or v.get("ja") or "") if isinstance(v, dict) else (v or "")


async def _site_issuer(lang, i):
    """FINORA operator info from the public-site 会社概要 (single source of truth) → (name, block, contact) or None."""
    s = ((await db.site_settings.find_one({"id": "main"})) or {}).get("data") or {}
    name = _loc(s.get("company_name"), lang)
    if not name:
        return None
    rep = _loc(s.get("representative"), lang)
    if rep and not any(w in rep for w in ("代表", "Director", "CEO", "Diretor")):
        rep = REP[i].format(n=rep)
    corp = _loc(s.get("corporate_number"), lang)
    block = (name, rep, _loc(s.get("address"), lang), CORP[i].format(n=corp) if corp else "")
    contact = " / ".join(x for x in (_loc(s.get("phone"), lang), _loc(s.get("email"), lang)) if x) or "-"
    return name, "\n".join(x for x in block if x), contact


async def _ctx(c):
    tm, i = c["terms"], LANGS[c["lang"]]
    tenant = await db.tenants.find_one({"id": c["tenant_id"]}) or {}
    if c["contract_type"] == "FINORA_SAAS":
        op = await db.users.find_one({"platform_admin": True}) or {}
        bp = ((await db.tenants.find_one({"id": op.get("tenant_id")})) or {}).get("billing_profile") or {}
        owner = await db.users.find_one({"id": tenant.get("owner_user_id")}) or {}
        recipient, consultant = f"{tenant.get('name')}（{owner.get('name', '')}）", owner.get("name")
        plan = await db.plans.find_one({"code": tm.get("plan_code")}) or {}
        fee = ("基本料金 ¥{b:,.0f} ＋ 顧客1人あたり ¥{p:,.0f} × 当月の最大顧客数（月額・税別）", "Base ¥{b:,.0f} + ¥{p:,.0f} per customer × monthly peak customers (monthly, excl. tax)",
               "Base ¥{b:,.0f} + ¥{p:,.0f} por cliente × pico mensal de clientes (mensal, sem impostos)")[i].format(b=plan.get("base_fee") or 0, p=plan.get("per_customer_fee") or 0)
        plan_name = plan.get("name") or tm.get("plan_code")
    else:
        bp = tenant.get("billing_profile") or {}
        cl = await db.clients.find_one({"id": c["client_id"]}) or {}
        recipient = cl.get("corporate_name") or cl.get("name") or "-"
        consultant = ((await db.users.find_one({"id": c.get("consultant_id")})) or {}).get("name")
        tax = {"exclusive": ("税別", "excl. tax", "sem impostos"), "inclusive": ("税込", "incl. tax", "com impostos"), "exempt": ("非課税", "tax exempt", "isento")}[tm["tax_mode"]][i]
        fee, plan_name = f"¥{tm['fee']:,.0f}（{CYCLE[tm['fee_type']][i]}・{tax}）", None
    issuer = bp.get("company_name") or "FINORA"
    block, contact = "\n".join(x for x in (issuer, bp.get("representative"), bp.get("address")) if x), " / ".join(x for x in (bp.get("phone"), bp.get("email")) if x) or "-"
    if c["contract_type"] == "FINORA_SAAS" and (site := await _site_issuer(c["lang"], i)):
        issuer, block, contact = site
    open_end = ("期間の定めなし", "no fixed end", "sem prazo final")[i]
    return {"issuer_name": issuer, "issuer_block": block, "issuer_contact": contact, "recipient_name": recipient,
            "consultant_name": consultant, "service": tm["service_name"], "description": tm.get("description") or "", "plan": plan_name,
            "fee_text": fee, "cycle": tm["fee_type"], "start_date": tm["start_date"], "term_text": f"{tm['start_date']} 〜 {tm.get('end_date') or open_end}",
            "renewal": (("期間満了時に同一条件で自動更新します。", "Renews automatically on the same terms.", "Renova-se automaticamente nas mesmas condições.")
                        if tm.get("auto_renew") else ("自動更新しません。", "Does not renew automatically.", "Não se renova automaticamente."))[i],
            "doc_date": date.today().isoformat(), "doc_version": f"Version {c['version']}.0"}


async def preview(c):
    ctx = await _ctx(c)
    return {k: build_sections(t, c["lang"], ctx, c.get("fields")) for k, t in zip(("important", "agreement"), DOC_TYPES[c["contract_type"]])}


async def _issue(c, which, actor_id):
    dtype = DOC_TYPES[c["contract_type"]][0 if which == "important" else 1]
    sections = (await preview(c))[which]
    doc = {"id": new_id(), "tenant_id": c["tenant_id"], "client_id": c.get("client_id"), "contract_id": c["id"], "contract_type": c["contract_type"],
           "document_type": dtype, "number": await _seq("platform" if c["contract_type"] == "FINORA_SAAS" else c["tenant_id"], PREFIX[dtype]),
           "version": f"{c['version']}.0", "lang": c["lang"], "title": doc_title(dtype, c["lang"]), "sections": sections, "created_at": now_iso(), "created_by": actor_id}
    doc["hash"] = _hash(doc)
    await db.econtract_docs.insert_one(doc)
    await db.econtracts.update_one({"id": c["id"]}, {"$set": {f"docs.{which}": doc["id"]}})
    return doc


def _hash(d):
    return hashlib.sha256(json.dumps({k: d[k] for k in ("contract_id", "document_type", "number", "version", "title", "sections")}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


async def _doc(c, which, verify=False):
    d = await db.econtract_docs.find_one({"id": (c.get("docs") or {}).get(which)})
    if not d or (verify and _hash(d) != d["hash"]):
        raise HTTPException(409, "Document missing or integrity check failed")
    return d


async def _move(c, frm, to, user, request, action, extra=None, doc=None):
    r = await db.econtracts.find_one_and_update({"id": c["id"], "status": {"$in": frm}}, {"$set": {"status": to, "updated_at": now_iso(), "updated_by": user["id"], **(extra or {})}},
                                                return_document=ReturnDocument.AFTER)
    if not r:
        raise HTTPException(409, f"This step is not allowed in status {c['status']}")
    await audit(user, action, "econtracts", c["id"], before={"status": c["status"]},
                after={"status": to, "contract_type": c["contract_type"], **({"document_id": doc["id"], "document_type": doc["document_type"], "document_version": doc["version"]} if doc else {})},
                request=request, client_id=c.get("client_id"), label=f"{c['number']} v{c['version']} {c['contract_type']}")
    return r


async def _act(c, doc, kind, party, user, request, **extra):
    ip, ua = _ipua(request)
    a = {"id": new_id(), "tenant_id": c["tenant_id"], "contract_id": c["id"], "contract_type": c["contract_type"], "client_id": c.get("client_id"),
         "consultant_id": c.get("consultant_id"), "document_id": doc["id"], "document_type": doc["document_type"], "document_version": doc["version"],
         "doc_hash": doc["hash"], "act": kind, "party": party, "user_id": user["id"], "user_email": user["email"], "at": now_iso(), "ip": ip, "user_agent": ua, **extra}
    await db.econtract_acts.insert_one(a)
    return a


async def _people(c, side):
    if (c["contract_type"], side) == ("FINORA_SAAS", "ISSUER"):
        return [(u["tenant_id"], u["id"]) for u in await db.users.find({"platform_admin": True}).to_list(20)]
    if c["contract_type"] == "FINORA_SAAS":
        return [(c["tenant_id"], u["id"]) for u in await db.users.find({"tenant_id": c["tenant_id"], "role": "admin", "active": {"$ne": False}}).to_list(20)]
    if side == "ISSUER":
        return [(c["tenant_id"], c.get("consultant_id"))]
    return [(c["tenant_id"], x) for x in await client_user_ids(c["tenant_id"], c["client_id"])]


async def _tell(c, side, kind, actor=None):
    link = f"/econtracts/{c['id']}"
    people = await _people(c, side)
    for tid, uid in people:
        await notify(tid, [uid], kind, {"label": f"{c['number']} {c['terms']['service_name']}", "contract_type": c["contract_type"]}, c.get("client_id"), link, actor)
    if kind in KINDS or kind == "econtract_ended":
        ctx = await _ctx(c)
        ec = {"id": c["id"], "tenant_id": c["tenant_id"], "lang": c.get("lang"), "number": c["number"], "service": c["terms"]["service_name"],
              "end_date": c.get("end_date") or ""}
        for _, uid in people:
            coro = send_ended_notice(uid, ec, "contract", ctx["issuer_name"], link) if kind == "econtract_ended" else send_sign_request(uid, c, kind, ctx["issuer_name"])
            task = asyncio.create_task(coro)
            _BG.add(task)
            task.add_done_callback(_BG.discard)


async def create_contract(user, body: ECIn, request, actor_id=None, parent=None):
    if body.contract_type == "CONSULTING":
        if user["role"] not in ("admin", "consultant") or not body.client_id:
            raise HTTPException(403, "Forbidden")
        await require_service(user)
        await scope(user, body.client_id)
        cl = await db.clients.find_one({"id": body.client_id, "tenant_id": user["tenant_id"]})
        tid, consultant_id = user["tenant_id"], cl.get("consultant_id") or user["id"]
    else:
        if not (user.get("platform_admin") or actor_id) or not body.tenant_id or not await db.tenants.find_one({"id": body.tenant_id}):
            raise HTTPException(403, "Forbidden")
        if not parent and await db.econtracts.find_one({"contract_type": "FINORA_SAAS", "tenant_id": body.tenant_id, "status": {"$in": PRE_ACTIVE + ["ACTIVE", "PAUSED"]}}):
            raise HTTPException(409, "An open FINORA contract already exists for this tenant")
        tid, consultant_id = body.tenant_id, None
    cid = new_id()
    c = {"id": cid, "tenant_id": tid, "contract_type": body.contract_type, "client_id": body.client_id if body.contract_type == "CONSULTING" else None,
         "consultant_id": consultant_id, "number": parent["number"] if parent else await _seq("platform" if body.contract_type == "FINORA_SAAS" else tid, "FS" if body.contract_type == "FINORA_SAAS" else "CC"),
         "version": parent["version"] + 1 if parent else 1, "root_id": parent["root_id"] if parent else cid, "parent_id": parent["id"] if parent else None,
         "status": "DRAFT", "lang": body.lang, "terms": body.terms.model_dump(), "fields": _fields(body.fields), "docs": {},
         "created_by": actor_id or user["id"], "created_at": now_iso(), "updated_at": now_iso()}
    await db.econtracts.insert_one(c)
    await audit(user, "create", "econtracts", cid, after={"contract_type": c["contract_type"], "version": c["version"], "status": "DRAFT"},
                request=request, client_id=c["client_id"], label=f"{c['number']} v{c['version']} {c['contract_type']}")
    return c


async def start_finora_contract(tenant_id, owner, request):
    """Signup: create the FINORA_SAAS contract and send the FINORA important-information statement automatically."""
    sub = await db.saas_subscriptions.find_one({"tenant_id": tenant_id}) or {}
    plan = sub.get("plan_code") if sub.get("plan_code") not in (None, "TRIAL", "FREE") else "STANDARD"
    body = ECIn(contract_type="FINORA_SAAS", tenant_id=tenant_id, lang=owner.get("lang") or "ja",
                terms=TermsIn(service_name="FINORA SaaS", description="", start_date=date.today().isoformat(), plan_code=plan))
    c = await create_contract(owner, body, request, actor_id="system")
    doc = await _issue(c, "important", "system")
    c = await _move(c, ["DRAFT"], "IMPORTANT_INFO_SENT", owner, request, "send_important", doc=doc)
    await _tell(c, "ISSUER", "econtract_new_signup")
    return c


def _sig_png(name):
    """Electronic approval stamp for FINORA's own (issuer) signature on FINORA_SAAS agreements."""
    from PIL import Image as PImage, ImageDraw, ImageFont
    img = PImage.new("RGB", (560, 160), "white")
    d = ImageDraw.Draw(img)
    f1 = ImageFont.truetype(str(Path(__file__).parent / "fonts" / "ipag.ttf"), 44)
    f2 = ImageFont.truetype(str(Path(__file__).parent / "fonts" / "ipag.ttf"), 20)
    d.text((24, 26), name, font=f1, fill="#071A2B")
    d.text((24, 96), "FINORA 電子承認 / Electronic approval", font=f2, fill="#0B6E4F")
    d.rectangle([(8, 8), (551, 151)], outline="#0B6E4F", width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def _auto_issuer_sign(c, request):
    """FINORA's counter-signature is applied automatically so a consultant can start using the service right after signing."""
    pa = await db.users.find_one({"platform_admin": True, "active": True})
    if not pa:
        return c
    t = await db.tenants.find_one({"id": pa["tenant_id"]}) or {}
    name = (t.get("billing_profile") or {}).get("company_name") or t.get("name") or "FINORA"
    d = await _doc(c, "agreement", verify=True)
    await _act(c, d, "SIGN", "ISSUER", pa, request, signer_name=name, signature_png=_sig_png(name), agreed_at=now_iso(), auto_signed=True)
    c = await _move(c, ["FIRST_PARTY_SIGNED"], "BOTH_SIGNED", pa, request, "sign", doc=d)
    return await _activate(c, pa, request)


async def _activate(c, user, request):
    c = await _move(c, ["BOTH_SIGNED"], "ACTIVE", user, request, "activate", extra={"activated_at": now_iso()})
    acts = await db.econtract_acts.find({"contract_id": c["id"], "act": {"$in": ["CONFIRM", "SIGN"]}}).to_list(20)
    for which, kind in (("important", "CONFIRM"), ("agreement", "SIGN")):
        d = await _doc(c, which)
        signs = [a | {"party_label": PARTY[(c["contract_type"], a["party"])][LANGS[c["lang"]]]} for a in acts if a["act"] == kind]
        fname = f"{d['title']}_{d['number']}_v{d['version']}.pdf"
        fid = await bucket.upload_from_stream(fname, render(d, c, signs), metadata={"tenant_id": c["tenant_id"], "content_type": "application/pdf"})
        await db.econtract_docs.update_one({"id": d["id"]}, {"$set": {"pdf_file_id": str(fid), "pdf_filename": fname, "finalized_at": now_iso()}})
        if c["contract_type"] == "CONSULTING":
            await db.documents.insert_one({"id": new_id(), "tenant_id": c["tenant_id"], "client_id": c["client_id"], "category": "contract", "filename": fname,
                                           "content_type": "application/pdf", "size": 0, "file_id": str(fid), "notes": f"{c['number']} v{c['version']}",
                                           "uploaded_by": "FINORA", "uploaded_by_role": "system", "created_at": now_iso()})
    if c.get("parent_id"):
        old = await db.econtracts.find_one_and_update({"id": c["parent_id"], "status": {"$in": ["ACTIVE", "PAUSED"]}},
                                                      {"$set": {"status": "ENDED", "ended_at": now_iso(), "end_reason": "AMENDED", "superseded_by": c["id"], "ended_by": user["id"]}})
        if old and old.get("billing_contract_id"):
            await db.contracts.update_one({"id": old["billing_contract_id"]}, {"$set": {"status": "ENDED", "updated_at": now_iso()}})
    tm = c["terms"]
    if c["contract_type"] == "FINORA_SAAS":
        await db.tenants.update_one({"id": c["tenant_id"]}, {"$set": {"status": "ACTIVE", "finora_contract": "ACTIVE"}})
        await db.saas_subscriptions.update_one({"tenant_id": c["tenant_id"]}, {"$set": {"plan_code": tm.get("plan_code") or "STANDARD", "status": "ACTIVE",
                                                                                        "start_date": tm["start_date"], "econtract_id": c["id"]}})
    else:
        bc = {"id": new_id(), "tenant_id": c["tenant_id"], "client_id": c["client_id"], "name": f"{tm['service_name']} ({c['number']} v{c['version']})",
              "service_name": tm["service_name"], "description": tm.get("description"), "fee_type": tm["fee_type"], "fee": tm["fee"], "tax_mode": tm["tax_mode"],
              "tax_rate": tm["tax_rate"], "start_date": tm["start_date"], "end_date": tm.get("end_date"), "billing_cycle": tm["fee_type"],
              "billing_day": tm["billing_day"], "payment_terms_days": tm["payment_terms_days"], "auto_renew": tm["auto_renew"], "status": "ACTIVE",
              "econtract_id": c["id"], "created_at": now_iso()}
        await db.contracts.insert_one(bc)
        await db.econtracts.update_one({"id": c["id"]}, {"$set": {"billing_contract_id": bc["id"]}})
        period = datetime.now().strftime("%Y-%m") if tm["fee_type"] == "MONTHLY" else datetime.now().strftime("%Y") if tm["fee_type"] == "YEARLY" else None
        inv = await build_invoice(user, InvoiceIn(client_id=c["client_id"], contract_id=bc["id"]), period)
        await db.invoices.insert_one(inv)
        await audit(user, "create", "invoices", inv["id"], after={"status": inv["status"], "econtract_id": c["id"]}, request=request, client_id=c["client_id"], label=inv["number"])
    await _tell(c, "RECIPIENT", "econtract_active", user)
    return c


def _next_invoice(c):
    tm = c["terms"]
    if c["status"] != "ACTIVE" or tm["fee_type"] not in ("MONTHLY", "YEARLY"):
        return None
    t = date.today()
    d = t.replace(day=tm["billing_day"])
    if d <= t:
        d = (d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)) if tm["fee_type"] == "MONTHLY" else d.replace(year=d.year + 1)
    return d.isoformat()


def _add_years(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return d.replace(year=d.year + n, day=28)


def renew_on(c, today=None):
    """Next renewal/expiry date of an ACTIVE contract (open-ended auto-renew → yearly anniversary of the start date)."""
    tm, t = c["terms"], today or date.today()
    if c["status"] != "ACTIVE" or not (tm.get("end_date") or tm.get("auto_renew")):
        return None
    if not tm.get("auto_renew"):
        d = date.fromisoformat(tm["end_date"])
        return d if d >= t else None
    base = date.fromisoformat(tm.get("end_date") or tm["start_date"])
    n = 0 if tm.get("end_date") else 1
    while _add_years(base, n) < t:
        n += 1
    return _add_years(base, n)


async def _row(c):
    r = clean(dict(c))
    rd = renew_on(c)
    r["renew_on"], r["renew_days"] = (rd.isoformat(), (rd - date.today()).days) if rd else (None, None)
    acts = await db.econtract_acts.find({"contract_id": c["id"], "act": {"$in": ["CONFIRM", "SIGN"]}}, {"_id": 0, "act": 1, "party": 1, "at": 1}).to_list(10)
    r["confirmed_at"] = next((a["at"] for a in acts if a["act"] == "CONFIRM"), None)
    r["recipient_signed_at"] = next((a["at"] for a in acts if a["act"] == "SIGN" and a["party"] == "RECIPIENT"), None)
    r["issuer_signed_at"] = next((a["at"] for a in acts if a["act"] == "SIGN" and a["party"] == "ISSUER"), None)
    r["next_invoice_date"] = _next_invoice(c)
    if c["contract_type"] == "FINORA_SAAS":
        t = await db.tenants.find_one({"id": c["tenant_id"]}) or {}
        owner = await db.users.find_one({"id": t.get("owner_user_id")}) or {}
        sub = await db.saas_subscriptions.find_one({"tenant_id": c["tenant_id"]}) or {}
        r |= {"tenant_name": t.get("name"), "owner_name": owner.get("name"), "owner_email": owner.get("email"), "plan_code": c["terms"].get("plan_code"),
              "fee_amount": (await customer_fee(c["tenant_id"]))["amount"], "payment_status": sub.get("payment_status"), "renewal_date": sub.get("renewal_date")}
    else:
        cl = await db.clients.find_one({"id": c["client_id"]}) or {}
        r["client_name"] = cl.get("corporate_name") or cl.get("name")
    return r


@router.get("")
async def list_contracts(type: str = "CONSULTING", client_id: Optional[str] = None, mine: bool = False, user=Depends(current)):
    if type == "FINORA_SAAS":
        if user.get("platform_admin") and not mine:
            q = {"contract_type": type}
        elif user["role"] == "admin":
            q = {"contract_type": type, "tenant_id": user["tenant_id"]}
        else:
            raise HTTPException(403, "Forbidden")
    else:
        q = {**await scope(user, client_id), "contract_type": "CONSULTING"}
        if user["role"] == "client":
            q["status"] = {"$ne": "DRAFT"}
    return [await _row(c) for c in await db.econtracts.find(q).sort("created_at", -1).to_list(1000)]


@router.get("/{cid}")
async def get_contract(cid: str, view_lang: Optional[str] = None, user=Depends(current)):
    c = await load(user, cid)
    docs = [clean(d) for d in await db.econtract_docs.find({"contract_id": cid}).to_list(20)]
    for d in docs:
        d["integrity_ok"] = _hash(d) == d["hash"]
    chain = await db.econtracts.find({"root_id": c["root_id"]}, {"_id": 0, "id": 1, "version": 1, "status": 1, "activated_at": 1, "ended_at": 1}).sort("version", 1).to_list(50)
    acts = [clean(a) for a in await db.econtract_acts.find({"contract_id": cid}, {"signature_png": 0}).sort("at", 1).to_list(500)]
    hist = [clean(a) for a in await db.audit_logs.find({"entity": "econtracts", "entity_id": cid}).sort("_id", 1).to_list(500)]
    msgs = [clean(m) for m in await db.message_log.find({"contract_id": cid}).sort("at", 1).to_list(200)] if is_issuer(user, c) else []
    out = await _row(c) | {"documents": docs, "versions": chain, "acts": acts, "history": hist, "messages": msgs,
                           "can_issue": is_issuer(user, c), "can_receive": is_recipient(user, c)}
    if c["status"] == "DRAFT" and is_issuer(user, c):
        out["preview"] = await preview(c)
    if view_lang in LANGS and view_lang != c["lang"]:
        out["view"] = await _translated(c, docs, view_lang)
    return out


async def _translated(c, docs, lang):
    """Reference translation in the viewer's language; the signed original (c.lang) stays authoritative. Free-text fields stay as written."""
    ctx = await _ctx({**c, "lang": lang})
    out = {"lang": lang, "original_lang": c["lang"]}
    for k, dtype in zip(("important", "agreement"), DOC_TYPES[c["contract_type"]]):
        d = next((x for x in docs if x["document_type"] == dtype), None)
        cx = ctx | ({"doc_date": d["created_at"][:10]} if d else {})
        out[k] = {"title": doc_title(dtype, lang), "sections": build_sections(dtype, lang, cx, c.get("fields"))}
    return out


@router.put("/{cid}")
async def update_draft(cid: str, body: ECIn, request: Request, user=Depends(current)):
    c = await load(user, cid)
    if not is_issuer(user, c) or c["status"] != "DRAFT":
        raise HTTPException(409, "Only drafts can be edited by the issuer")
    upd = {"lang": body.lang, "terms": body.terms.model_dump(), "fields": _fields(body.fields), "updated_at": now_iso(), "updated_by": user["id"]}
    await db.econtracts.update_one({"id": cid, "status": "DRAFT"}, {"$set": upd})
    await audit(user, "update", "econtracts", cid, before={"terms": c["terms"]}, after={"terms": upd["terms"]}, request=request, client_id=c.get("client_id"),
                label=f"{c['number']} v{c['version']} {c['contract_type']}")
    return await get_contract(cid, user)


@router.post("")
async def create(body: ECIn, request: Request, user=Depends(current)):
    return clean(await create_contract(user, body, request))


def _need(ok, msg="Forbidden"):
    if not ok:
        raise HTTPException(403, msg)


@router.post("/{cid}/send-important")
async def send_important(cid: str, request: Request, user=Depends(current)):
    c = await load(user, cid)
    _need(is_issuer(user, c))
    if c["status"] != "DRAFT":
        raise HTTPException(409, f"This step is not allowed in status {c['status']}")
    doc = await _issue(c, "important", user["id"])
    c = await _move(c, ["DRAFT"], "IMPORTANT_INFO_SENT", user, request, "send_important", doc=doc)
    await _tell(c, "RECIPIENT", "econtract_important_sent", user)
    return {"status": c["status"]}


REISSUE = {"IMPORTANT_INFO_SENT": "important", "CONTRACT_SENT": "agreement"}


@router.post("/{cid}/reissue")
async def reissue(cid: str, request: Request, user=Depends(current)):
    """Re-issue the sent-but-not-yet-confirmed/signed document with current data; the old one is kept as superseded."""
    c = await load(user, cid)
    _need(is_issuer(user, c))
    which = REISSUE.get(c["status"])
    if not which:
        raise HTTPException(409, f"This step is not allowed in status {c['status']}")
    old = await _doc(c, which)
    doc = await _issue(c, which, user["id"])
    await db.econtract_docs.update_one({"id": old["id"]}, {"$set": {"superseded_by": doc["id"], "superseded_at": now_iso()}})
    await audit(user, "reissue", "econtracts", cid, before={"document_id": old["id"], "number": old["number"], "hash": old["hash"]},
                after={"document_id": doc["id"], "number": doc["number"], "document_type": doc["document_type"], "hash": doc["hash"]},
                request=request, client_id=c.get("client_id"), label=f"{c['number']} v{c['version']} {c['contract_type']}")
    return {"status": c["status"], "document_id": doc["id"], "number": doc["number"]}


@router.post("/{cid}/view/{doc_id}")
async def view_doc(cid: str, doc_id: str, request: Request, user=Depends(current)):
    c = await load(user, cid)
    d = await db.econtract_docs.find_one({"id": doc_id, "contract_id": cid})
    if not d:
        raise HTTPException(404, "Not found")
    await _act(c, d, "VIEW", "RECIPIENT" if is_recipient(user, c) else "ISSUER", user, request)
    await audit(user, "view", "econtracts", cid, after={"document_id": doc_id, "document_type": d["document_type"], "document_version": d["version"]},
                request=request, client_id=c.get("client_id"), label=f"{c['number']} {d['number']}")
    return {"ok": True}


@router.post("/{cid}/confirm")
async def confirm(cid: str, request: Request, user=Depends(current)):
    c = await load(user, cid)
    _need(is_recipient(user, c), "Only the recipient can confirm the statement")
    if c["status"] != "IMPORTANT_INFO_SENT":
        raise HTTPException(409, f"This step is not allowed in status {c['status']}")
    d = await _doc(c, "important", verify=True)
    now = now_iso()
    await _act(c, d, "CONFIRM", "RECIPIENT", user, request, confirmed_at=now, agreed_at=now)
    c = await _move(c, ["IMPORTANT_INFO_SENT"], "IMPORTANT_INFO_CONFIRMED", user, request, "confirm_important", doc=d)
    await _tell(c, "ISSUER", "econtract_important_confirmed", user)
    if c["contract_type"] == "FINORA_SAAS":
        doc = await _issue(c, "agreement", "system")
        c = await _move(c, ["IMPORTANT_INFO_CONFIRMED"], "CONTRACT_SENT", user, request, "send_agreement", doc=doc)
    return {"status": c["status"]}


@router.post("/{cid}/send-agreement")
async def send_agreement(cid: str, request: Request, user=Depends(current)):
    c = await load(user, cid)
    _need(is_issuer(user, c))
    if c["status"] != "IMPORTANT_INFO_CONFIRMED" or not await db.econtract_acts.find_one({"contract_id": cid, "act": "CONFIRM"}):
        raise HTTPException(409, "The important-information statement must be confirmed first")
    doc = await _issue(c, "agreement", user["id"])
    c = await _move(c, ["IMPORTANT_INFO_CONFIRMED"], "CONTRACT_SENT", user, request, "send_agreement", doc=doc)
    await _tell(c, "RECIPIENT", "econtract_agreement_sent", user)
    return {"status": c["status"]}


@router.post("/{cid}/sign")
async def sign(cid: str, body: SignIn, request: Request, user=Depends(current)):
    c = await load(user, cid)
    if not body.agree or not body.signature_png.startswith("data:image/png;base64,"):
        raise HTTPException(422, "Agreement and a handwritten signature are required")
    if not await db.econtract_acts.find_one({"contract_id": cid, "act": "CONFIRM"}):
        raise HTTPException(409, "The important-information statement must be confirmed first")
    d = await _doc(c, "agreement", verify=True)
    if is_recipient(user, c) and c["status"] == "CONTRACT_SENT":
        await _act(c, d, "SIGN", "RECIPIENT", user, request, signer_name=body.name, signature_png=body.signature_png, agreed_at=now_iso())
        c = await _move(c, ["CONTRACT_SENT"], "FIRST_PARTY_SIGNED", user, request, "sign", doc=d)
        await _tell(c, "ISSUER", "econtract_recipient_signed", user)
        if c["contract_type"] == "FINORA_SAAS":
            c = await _auto_issuer_sign(c, request)
    elif is_issuer(user, c) and c["status"] == "FIRST_PARTY_SIGNED":
        await _act(c, d, "SIGN", "ISSUER", user, request, signer_name=body.name, signature_png=body.signature_png, agreed_at=now_iso())
        c = await _move(c, ["FIRST_PARTY_SIGNED"], "BOTH_SIGNED", user, request, "sign", doc=d)
        c = await _activate(c, user, request)
    else:
        raise HTTPException(409, "Signing order: the recipient signs first, then the issuer")
    return {"status": c["status"]}


@router.post("/{cid}/cancel")
async def cancel(cid: str, body: Dict[str, str], request: Request, user=Depends(current)):
    c = await load(user, cid)
    _need(is_issuer(user, c))
    c = await _move(c, PRE_ACTIVE + ["BOTH_SIGNED"], "CANCELLED", user, request, "cancel", extra={"cancel_reason": (body.get("reason") or "")[:1000]})
    return {"status": c["status"]}


@router.post("/{cid}/pause")
async def pause(cid: str, request: Request, user=Depends(current)):
    c = await load(user, cid)
    _need(is_issuer(user, c))
    to, frm = ("ACTIVE", "PAUSED") if c["status"] == "PAUSED" else ("PAUSED", "ACTIVE")
    c = await _move(c, [frm], to, user, request, "resume" if to == "ACTIVE" else "pause")
    if c["contract_type"] == "FINORA_SAAS":
        await db.tenants.update_one({"id": c["tenant_id"]}, {"$set": {"finora_contract": to, "status": to}})
    elif c.get("billing_contract_id"):
        await db.contracts.update_one({"id": c["billing_contract_id"]}, {"$set": {"status": to}})
    return {"status": c["status"]}


@router.post("/{cid}/end")
async def end(cid: str, body: EndIn, request: Request, user=Depends(current)):
    c = await load(user, cid)
    _need(is_issuer(user, c))
    extra = {"end_date": body.end_date, "end_reason": body.reason, "ended_at": now_iso(), "ended_by": user["id"], "ended_by_name": user.get("name")}
    if c["contract_type"] == "FINORA_SAAS":
        extra["end_policy"] = {"consultant_login": body.consultant_login, "client_access": body.client_access, "retention_days": body.retention_days}
    c = await _move(c, ["ACTIVE", "PAUSED"], "ENDED", user, request, "end", extra=extra)
    if c["contract_type"] == "FINORA_SAAS":
        await db.tenants.update_one({"id": c["tenant_id"]}, {"$set": {"finora_contract": "ENDED", "status": "ENDED", "end_policy": extra["end_policy"]}})
    elif c.get("billing_contract_id"):
        await db.contracts.update_one({"id": c["billing_contract_id"]}, {"$set": {"status": "ENDED", "end_date": body.end_date}})
    await _tell(c, "RECIPIENT", "econtract_ended", user)
    return {"status": c["status"]}


@router.post("/{cid}/amend")
async def amend(cid: str, request: Request, user=Depends(current)):
    c = await load(user, cid)
    _need(is_issuer(user, c))
    if c["status"] not in ("ACTIVE", "PAUSED") or await db.econtracts.find_one({"parent_id": cid, "status": {"$in": PRE_ACTIVE + ["BOTH_SIGNED"]}}):
        raise HTTPException(409, "Only active contracts without an open amendment can be amended")
    body = ECIn(contract_type=c["contract_type"], client_id=c.get("client_id"), tenant_id=c["tenant_id"], lang=c["lang"], terms=TermsIn(**c["terms"]), fields=c.get("fields") or {})
    new = await create_contract(user, body, request, actor_id=user["id"], parent=c)
    return clean(new)


@router.get("/{cid}/docs/{doc_id}/pdf")
async def pdf(cid: str, doc_id: str, request: Request, user=Depends(current)):
    from bson import ObjectId
    c = await load(user, cid)
    d = await db.econtract_docs.find_one({"id": doc_id, "contract_id": cid})
    if not d or not d.get("pdf_file_id"):
        raise HTTPException(404, "PDF is generated when the contract becomes active")
    data = await (await bucket.open_download_stream(ObjectId(d["pdf_file_id"]))).read()
    await audit(user, "download", "econtracts", cid, after={"document_id": doc_id, "document_type": d["document_type"], "document_version": d["version"]},
                request=request, client_id=c.get("client_id"), label=f"{c['number']} {d['number']}.pdf")
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{d["number"]}.pdf"'})
