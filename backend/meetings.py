"""1:1 consulting video meetings: scheduling + notices, REST-polling WebRTC signaling, low-quality recording upload, AI minutes, 3-year retention."""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage
from emergentintegrations.llm.openai import OpenAISpeechToText
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core import audit, client_user_ids, current, db, new_id, notify, now_iso, scope
from sign_notify import APP_URL, TXT, _deliver

logger = logging.getLogger("meetings")
router = APIRouter(prefix="/api/meetings")
DIR = Path(os.environ["MEETING_DIR"])
DIR.mkdir(parents=True, exist_ok=True)
_BG = set()
MINUTES_PROMPT = ("あなたは資産運用コンサルティング会社の議事録作成担当です。会議の文字起こしから、簡潔な議事録を作成します。"
                  "文字起こしの言語に関わらず、同じ内容を日本語・英語・ポルトガル語の3言語で作成してください。"
                  "各言語で、見出しは「概要」「話し合った内容」「決定事項」「今後の対応（担当・期限）」に相当する構成とし、推測で事実を補わないこと。"
                  '出力は必ず次のJSON形式のみ（前後に説明やコードフェンスを付けない）: '
                  '{"ja": "<日本語の議事録>", "en": "<English minutes>", "pt": "<ata em português>"}')
LANGS = ("ja", "en", "pt")
NOTICE = {
    "ja": {"new": ("【FINORA】テレビ電話のご予約（{when}）", "{who}とのテレビ電話「{title}」を {when} に予約しました。時間になりましたらFINORAの「通話に参加」からご参加ください。"),
           "soon": ("【FINORA】まもなくテレビ電話が始まります（{when}）", "テレビ電話「{title}」が {when} に始まります。FINORAの「通話に参加」からご参加ください。"),
           "cancel": ("【FINORA】テレビ電話のキャンセル（{when}）", "{when} に予定していたテレビ電話「{title}」はキャンセルされました。"),
           "minutes": ("【FINORA】議事録が届きました（{title}）", "{when} のテレビ電話「{title}」の議事録が届きました。FINORAのコンサルティング画面からご確認ください。"), "cta": "FINORAで確認する"},
    "en": {"new": ("[FINORA] Video call scheduled ({when})", "A video call \"{title}\" with {who} is scheduled for {when}. Please join from \"Join call\" in FINORA."),
           "soon": ("[FINORA] Your video call starts soon ({when})", "The video call \"{title}\" starts at {when}. Please join from \"Join call\" in FINORA."),
           "cancel": ("[FINORA] Video call cancelled ({when})", "The video call \"{title}\" scheduled for {when} was cancelled."),
           "minutes": ("[FINORA] Meeting minutes are ready ({title})", "The minutes of the video call \"{title}\" on {when} are ready. Please check them on the Consulting page in FINORA."), "cta": "Open FINORA"},
    "pt": {"new": ("[FINORA] Videochamada agendada ({when})", "A videochamada \"{title}\" com {who} foi agendada para {when}. Entre por \"Entrar na chamada\" no FINORA."),
           "soon": ("[FINORA] Sua videochamada começa em breve ({when})", "A videochamada \"{title}\" começa às {when}. Entre por \"Entrar na chamada\" no FINORA."),
           "cancel": ("[FINORA] Videochamada cancelada ({when})", "A videochamada \"{title}\" agendada para {when} foi cancelada."),
           "minutes": ("[FINORA] A ata da reunião está disponível ({title})", "A ata da videochamada \"{title}\" de {when} está disponível. Confira na página de Consultoria do FINORA."), "cta": "Abrir o FINORA"},
}
ICS_KIND = {"new": "REQUEST", "cancel": "CANCEL"}
STAFF_ONLY = ("minutes", "minutes_i18n", "transcript", "minutes_error")


def _parse_i18n(out):
    s = (out or "").strip()
    i, j = s.find("{"), s.rfind("}")
    if i >= 0 and j > i:
        try:
            d = json.loads(s[i:j + 1])
            return {k: str(d[k]).strip() for k in LANGS if d.get(k)}
        except (ValueError, TypeError):
            pass
    return {}


def _i18n_of(m, field="minutes"):
    d = m.get(f"{field}_i18n")
    if d:
        return dict(d)
    return {"ja": m[field]} if m.get(field) else {}


def _ics(m, method, email):
    fmt = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    start = datetime.fromisoformat(m["scheduled_at"])
    esc = lambda s: s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")  # noqa: E731
    url = f"{APP_URL}/consulting"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FINORA//Meetings//JA", f"METHOD:{method}", "BEGIN:VEVENT",
             f"UID:{m['id']}@finora.co.jp", f"DTSTAMP:{fmt(datetime.now(timezone.utc))}", f"DTSTART:{fmt(start)}",
             f"DTEND:{fmt(start + timedelta(minutes=m['duration_min']))}", f"SUMMARY:{esc('FINORA テレビ電話: ' + m['title'])}",
             f"DESCRIPTION:{esc('FINORAの「通話に参加」からご参加ください / Join from FINORA: ' + url)}", f"URL:{url}", "LOCATION:FINORA",
             f"ORGANIZER;CN=FINORA:mailto:{os.environ['EMAIL_FROM']}", f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=FALSE:mailto:{email}",
             f"SEQUENCE:{1 if method == 'CANCEL' else 0}", f"STATUS:{'CANCELLED' if method == 'CANCEL' else 'CONFIRMED'}", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def _view(m, user):
    if user["role"] == "client":
        return {k: v for k, v in m.items() if k not in STAFF_ONLY}
    return {k: v for k, v in m.items() if k != "transcript"}


class MeetIn(BaseModel):
    client_id: str
    title: str = Field(min_length=1, max_length=200)
    scheduled_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
    duration_min: int = Field(60, ge=15, le=240)
    request_id: Optional[str] = None


class SignalIn(BaseModel):
    type: str = Field(pattern="^(hello|offer|answer|ice|rec|share|leave|bye)$")
    data: Dict[str, Any] = {}


class MinutesIn(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    lang: str = Field("ja", pattern="^(ja|en|pt)$")


def _staff(user):
    if user["role"] not in ("admin", "consultant"):
        raise HTTPException(403, "Forbidden")


async def _load(user, mid):
    m = await db.meetings.find_one({"id": mid, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Not found")
    await scope(user, m["client_id"])
    return m


def _when(m):
    dt = datetime.fromisoformat(m["scheduled_at"]).astimezone(timezone(timedelta(hours=9)))
    return dt.strftime("%Y-%m-%d %H:%M") + " JST"


async def _tell(m, kind, actor=None, both=False):
    uids = list(await client_user_ids(m["tenant_id"], m["client_id"])) + ([m["consultant_id"]] if both else [])
    await notify(m["tenant_id"], uids, f"meeting_{kind}", {"label": m["title"]}, m["client_id"], "/consulting", actor)
    who = (await db.users.find_one({"id": m["consultant_id"]}, {"name": 1}) or {}).get("name") or "FINORA"
    cl = await db.clients.find_one({"id": m["client_id"]}, {"name": 1, "corporate_name": 1}) or {}
    for uid in set(uids):
        u = await db.users.find_one({"id": uid})
        if not u:
            continue
        lang = u.get("lang") if u.get("lang") in NOTICE else "ja"
        other = (cl.get("corporate_name") or cl.get("name") or "") if uid == m["consultant_id"] else who
        subject, body = (s.format(when=_when(m), title=m["title"], who=other) for s in NOTICE[lang][kind])
        method = ICS_KIND.get(kind)
        task = asyncio.create_task(_deliver({"id": m["id"], "tenant_id": m["tenant_id"], "number": m["title"]}, u, "meeting", TXT[lang], subject, body,
                                            NOTICE[lang]["cta"], "/consulting", ics=_ics(m, method, u["email"]) if method else None, ics_method=method or "REQUEST"))
        _BG.add(task)
        task.add_done_callback(_BG.discard)


def _sig(mid, exp):
    return hmac.new(os.environ["JWT_SECRET"].encode(), f"{mid}:{exp}".encode(), hashlib.sha256).hexdigest()


@router.get("/ice")
async def ice(user=Depends(current)):
    servers = [{"urls": "stun:stun.l.google.com:19302"}]
    if os.environ["TURN_URL"]:
        servers.append({"urls": os.environ["TURN_URL"].split(","), "username": os.environ["TURN_USER"], "credential": os.environ["TURN_PASS"]})
    return {"iceServers": servers}


@router.get("")
async def list_meetings(client_id: Optional[str] = None, user=Depends(current)):
    q = await scope(user, client_id)
    rows = await db.meetings.find(q, {"_id": 0, "transcript": 0}).sort("scheduled_at", -1).to_list(300)
    names = {c["id"]: c.get("corporate_name") or c.get("name") for c in await db.clients.find({"tenant_id": user["tenant_id"]}, {"id": 1, "name": 1, "corporate_name": 1}).to_list(5000)}
    return [_view(r, user) | {"client_name": names.get(r["client_id"])} for r in rows]


@router.get("/{mid}")
async def get_meeting(mid: str, user=Depends(current)):
    m = await _load(user, mid)
    cl = await db.clients.find_one({"id": m["client_id"]}, {"name": 1, "corporate_name": 1})
    co = await db.users.find_one({"id": m["consultant_id"]}, {"name": 1})
    return _view(m, user) | {"client_name": (cl or {}).get("corporate_name") or (cl or {}).get("name"), "consultant_name": (co or {}).get("name")}


@router.post("")
async def create(body: MeetIn, request: Request, user=Depends(current)):
    _staff(user)
    await scope(user, body.client_id)
    datetime.fromisoformat(body.scheduled_at)
    if body.request_id and not await db.requests.find_one({"id": body.request_id, "client_id": body.client_id, "tenant_id": user["tenant_id"]}, {"_id": 1}):
        raise HTTPException(404, "Not found")
    m = {"id": new_id(), "tenant_id": user["tenant_id"], "client_id": body.client_id, "consultant_id": user["id"], "title": body.title,
         "scheduled_at": body.scheduled_at, "duration_min": body.duration_min, "request_id": body.request_id, "status": "SCHEDULED",
         "reminded": False, "created_at": now_iso(), "expires_at": (datetime.now(timezone.utc) + timedelta(days=365 * 3)).isoformat()}
    await db.meetings.insert_one(dict(m))
    await audit(user, "create", "meetings", m["id"], after={"title": m["title"], "scheduled_at": m["scheduled_at"]}, request=request, client_id=m["client_id"], label=m["title"])
    if body.request_id:
        await db.requests.update_one({"id": body.request_id}, {"$set": {"video_meeting_id": m["id"], "video_meeting_at": m["scheduled_at"]}})
    await _tell(m, "new", user, both=True)
    m.pop("_id", None)
    return m


@router.post("/{mid}/cancel")
async def cancel(mid: str, request: Request, user=Depends(current)):
    _staff(user)
    m = await _load(user, mid)
    if m["status"] != "SCHEDULED":
        raise HTTPException(409, f"This step is not allowed in status {m['status']}")
    await db.meetings.update_one({"id": mid}, {"$set": {"status": "CANCELLED"}})
    await audit(user, "cancel", "meetings", mid, request=request, client_id=m["client_id"], label=m["title"])
    await db.requests.update_many({"video_meeting_id": mid}, {"$unset": {"video_meeting_id": "", "video_meeting_at": ""}})
    await _tell(m, "cancel", user, both=True)
    return {"status": "CANCELLED"}


@router.get("/{mid}/transcript")
async def transcript(mid: str, user=Depends(current)):
    _staff(user)
    m = await db.meetings.find_one({"id": (await _load(user, mid))["id"]}, {"transcript": 1})
    return {"transcript": m.get("transcript") or ""}


@router.put("/{mid}/minutes")
async def edit_minutes(mid: str, body: MinutesIn, request: Request, user=Depends(current)):
    _staff(user)
    m = await _load(user, mid)
    if m.get("minutes_status") not in ("DRAFT", "APPROVED"):
        raise HTTPException(409, f"This step is not allowed in status {m.get('minutes_status')}")
    i18n = _i18n_of(m, "minutes")
    i18n[body.lang] = body.text
    upd = {"minutes_i18n": i18n, "minutes_status": "DRAFT", "minutes_edited_at": now_iso(), "minutes_edited_by": user["id"]}
    if body.lang == "ja":
        upd["minutes"] = body.text
    await db.meetings.update_one({"id": mid}, {"$set": upd})
    await audit(user, "edit_minutes", "meetings", mid, request=request, client_id=m["client_id"], label=m["title"])
    return {"minutes_status": "DRAFT"}


@router.post("/{mid}/minutes/approve")
async def approve_minutes(mid: str, request: Request, user=Depends(current)):
    _staff(user)
    m = await _load(user, mid)
    i18n = _i18n_of(m, "minutes")
    if m.get("minutes_status") != "DRAFT" or not i18n:
        raise HTTPException(409, f"This step is not allowed in status {m.get('minutes_status')}")
    primary = i18n.get("ja") or next(iter(i18n.values()))
    await db.meetings.update_one({"id": mid}, {"$set": {"minutes_approved_i18n": i18n, "minutes_approved": primary, "minutes_status": "APPROVED",
                                                        "minutes_approved_at": now_iso(), "minutes_approved_by": user["id"], "minutes_approved_by_name": user.get("name")}})
    await audit(user, "approve_minutes", "meetings", mid, request=request, client_id=m["client_id"], label=m["title"])
    await _tell(m, "minutes", user)
    return {"minutes_status": "APPROVED"}


@router.post("/{mid}/end")
async def end(mid: str, user=Depends(current)):
    _staff(user)
    await _load(user, mid)
    await db.meetings.update_one({"id": mid, "status": {"$in": ["SCHEDULED", "LIVE"]}}, {"$set": {"status": "ENDED", "ended_at": now_iso()}})
    return {"status": "ENDED"}


@router.post("/{mid}/signal")
async def signal(mid: str, body: SignalIn, user=Depends(current)):
    m = await _load(user, mid)
    if m["status"] == "CANCELLED":
        raise HTTPException(409, "This step is not allowed in status CANCELLED")
    if body.type == "hello" and m["status"] == "SCHEDULED":
        await db.meetings.update_one({"id": mid}, {"$set": {"status": "LIVE", "started_at": now_iso()}})
    await db.meeting_signals.insert_one({"mid": mid, "from": user["id"], "type": body.type, "data": body.data, "at": time.time(), "created": datetime.now(timezone.utc)})
    return {"ok": True}


@router.get("/{mid}/signal")
async def poll(mid: str, since: float = 0, user=Depends(current)):
    await _load(user, mid)
    since = since or time.time() - 60
    rows = await db.meeting_signals.find({"mid": mid, "at": {"$gt": since}, "from": {"$ne": user["id"]}}, {"_id": 0, "created": 0}).sort("at", 1).to_list(200)
    return rows


@router.post("/{mid}/recording/{kind}/chunk")
async def chunk(mid: str, kind: str, idx: int, request: Request, user=Depends(current)):
    _staff(user)
    await _load(user, mid)
    if kind not in ("video", "audio"):
        raise HTTPException(404, "Not found")
    data = await request.body()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Chunk too large")
    with open(DIR / f"{mid}_{kind}.webm", "wb" if idx == 0 else "ab") as f:
        f.write(data)
    return {"ok": True}


@router.post("/{mid}/recording/done")
async def done(mid: str, request: Request, user=Depends(current)):
    _staff(user)
    m = await _load(user, mid)
    video = DIR / f"{mid}_video.webm"
    if not video.exists():
        raise HTTPException(404, "Not found")
    await db.meetings.update_one({"id": mid}, {"$set": {"recording": {"size": video.stat().st_size, "at": now_iso()}, "minutes_status": "PROCESSING"}})
    await audit(user, "record", "meetings", mid, request=request, client_id=m["client_id"], label=m["title"])
    task = asyncio.create_task(make_minutes(mid))
    _BG.add(task)
    task.add_done_callback(_BG.discard)
    return {"ok": True}


@router.get("/{mid}/recording-url")
async def recording_url(mid: str, user=Depends(current)):
    m = await _load(user, mid)
    if not m.get("recording") or m.get("recording_deleted"):
        raise HTTPException(404, "Not found")
    exp = int(time.time()) + 3600
    return {"url": f"/api/meetings/{mid}/media?exp={exp}&sig={_sig(mid, exp)}"}


@router.get("/{mid}/media")
async def media(mid: str, exp: int, sig: str):
    if exp < time.time() or not hmac.compare_digest(sig, _sig(mid, exp)) or not (DIR / f"{mid}_video.webm").exists():
        raise HTTPException(404, "Not found")
    return FileResponse(DIR / f"{mid}_video.webm", media_type="video/webm")


async def make_minutes(mid):
    m = await db.meetings.find_one({"id": mid})
    audio = DIR / f"{mid}_audio.webm"
    try:
        if not audio.exists() or audio.stat().st_size > 25 * 1024 * 1024:
            raise RuntimeError("audio missing or larger than 25MB")
        stt = OpenAISpeechToText(api_key=os.environ["EMERGENT_LLM_KEY"])
        with open(audio, "rb") as f:
            text = (await stt.transcribe(file=f, model="whisper-1", response_format="json")).text
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"minutes-{mid}", system_message=MINUTES_PROMPT).with_model("anthropic", "claude-sonnet-4-6")
        out = ""
        async for ev in chat.stream_message(UserMessage(text=f"会議名: {m['title']}\n日時: {_when(m)}\n\n文字起こし:\n{text[:60000]}")):
            if isinstance(ev, TextDelta):
                out += ev.content
            elif isinstance(ev, StreamDone):
                break
        i18n = _parse_i18n(out) or {"ja": out.strip()}
        primary = i18n.get("ja") or next(iter(i18n.values()))
        await db.meetings.update_one({"id": mid}, {"$set": {"transcript": text, "minutes_i18n": i18n, "minutes": primary, "minutes_status": "DRAFT", "minutes_at": now_iso()}})
    except Exception as e:  # noqa: BLE001
        logger.exception("minutes failed %s", mid)
        await db.meetings.update_one({"id": mid}, {"$set": {"minutes_status": "FAILED", "minutes_error": str(e)[:300]}})


async def loop():
    await db.meeting_signals.create_index("created", expireAfterSeconds=86400)
    await db.meeting_signals.create_index([("mid", 1), ("at", 1)])
    while True:
        try:
            now = datetime.now(timezone.utc)
            for m in await db.meetings.find({"status": "SCHEDULED", "reminded": False}).to_list(500):
                if now <= datetime.fromisoformat(m["scheduled_at"]) <= now + timedelta(minutes=15):
                    await db.meetings.update_one({"id": m["id"]}, {"$set": {"reminded": True}})
                    await _tell(m, "soon", both=True)
            for m in await db.meetings.find({"expires_at": {"$lt": now.isoformat()}, "recording_deleted": {"$ne": True}, "recording": {"$exists": True}}).to_list(500):
                for k in ("video", "audio"):
                    (DIR / f"{m['id']}_{k}.webm").unlink(missing_ok=True)
                await db.meetings.update_one({"id": m["id"]}, {"$set": {"recording_deleted": True}})
        except Exception:
            logger.exception("meetings loop failed")
        await asyncio.sleep(60)
