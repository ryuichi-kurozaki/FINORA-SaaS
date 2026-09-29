"""LINE 応答（Reply）方式の通知。無料枠の対象外となる応答メッセージのみを使うため、通数無制限・完全無料。

ユーザーが FINORA の LINE 公式アカウントにキーワードを送ると、その場で最新情報を返信する。
（プッシュ送信は行わない。LINE 側の仕様上、こちらから先に送るには有料枠が必要なため）
"""
import base64
import hashlib
import hmac
import logging
import os
import random
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from core import audit, current, db, new_id, now_iso

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/line")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
BOT_BASIC_ID = os.environ.get("LINE_BOT_BASIC_ID", "")
LINE_API = "https://api.line.me/v2/bot"
CODE_TTL_MIN = 30

TXT = {
    "ja": {
        "menu": "FINORA 通知ボットです。次のキーワードを送ると最新情報をお返しします。\n\n"
                "・通知 … 未読のお知らせ\n・請求 … 未払いの請求書\n・契約 … 対応が必要な契約\n"
                "・面談 … 今後のテレビ電話・面談\n・資産 … 資産評価額\n・ヘルプ … このメニュー",
        "need_link": "まだFINORAのアカウントと連携されていません。\nFINORAにログインし「設定 → 通知設定 → LINE連携」で6桁の連携コードを発行し、その番号をこのトークに送ってください。",
        "linked": "{name} 様のFINORAアカウントと連携しました。\n「ヘルプ」と送るとメニューを表示します。",
        "bad_code": "連携コードが正しくないか、有効期限（30分）が切れています。FINORAで再発行してください。",
        "already": "このLINEアカウントは既に別のFINORAアカウントと連携されています。先に連携を解除してください。",
        "notif": "未読のお知らせ（{n}件）", "notif_none": "未読のお知らせはありません。",
        "inv": "未払いの請求書（{n}件）", "inv_none": "未払いの請求書はありません。",
        "inv_row": "・{number}　{amount}　支払期限 {due}",
        "ec": "対応が必要な契約（{n}件）", "ec_none": "対応が必要な契約はありません。",
        "ec_row": "・{number}　{service}　{status}",
        "mt": "今後のご予約（{n}件）", "mt_none": "今後のご予約はありません。",
        "mt_row": "・{when}　{title}",
        "assets": "資産評価額：{amount}\n（{n}件の保有資産、{date} 時点）",
        "assets_none": "登録されている資産がありません。",
        "staff": "スタッフ用：未払い請求 {inv}件／対応待ち契約 {ec}件／今後の面談 {mt}件",
        "unknown": "キーワードが分かりませんでした。「ヘルプ」と送るとメニューを表示します。",
        "open": "FINORAで詳しく見る：{url}",
    },
    "en": {
        "menu": "FINORA notification bot. Send one of these keywords to get the latest information.\n\n"
                "・notice … unread notifications\n・invoice … unpaid invoices\n・contract … contracts needing action\n"
                "・meeting … upcoming meetings\n・assets … portfolio value\n・help … this menu",
        "need_link": "Your LINE account is not linked yet.\nLog in to FINORA, go to Settings → Notifications → LINE, issue a 6-digit code and send it in this chat.",
        "linked": "Linked to the FINORA account of {name}.\nSend \"help\" to see the menu.",
        "bad_code": "The code is invalid or expired (30 minutes). Please issue a new one in FINORA.",
        "already": "This LINE account is already linked to another FINORA account. Please unlink it first.",
        "notif": "Unread notifications ({n})", "notif_none": "No unread notifications.",
        "inv": "Unpaid invoices ({n})", "inv_none": "No unpaid invoices.",
        "inv_row": "・{number}  {amount}  due {due}",
        "ec": "Contracts needing action ({n})", "ec_none": "No contracts need your action.",
        "ec_row": "・{number}  {service}  {status}",
        "mt": "Upcoming meetings ({n})", "mt_none": "No upcoming meetings.",
        "mt_row": "・{when}  {title}",
        "assets": "Portfolio value: {amount}\n({n} holdings, as of {date})",
        "assets_none": "No assets registered.",
        "staff": "Staff: {inv} unpaid invoices / {ec} contracts awaiting action / {mt} upcoming meetings",
        "unknown": "Keyword not recognised. Send \"help\" to see the menu.",
        "open": "See details in FINORA: {url}",
    },
    "pt": {
        "menu": "Bot de notificações FINORA. Envie uma destas palavras para receber as informações mais recentes.\n\n"
                "・aviso … notificações não lidas\n・fatura … faturas em aberto\n・contrato … contratos pendentes\n"
                "・reuniao … próximas reuniões\n・ativos … valor da carteira\n・ajuda … este menu",
        "need_link": "Sua conta LINE ainda não está vinculada.\nEntre no FINORA, vá em Configurações → Notificações → LINE, gere um código de 6 dígitos e envie-o nesta conversa.",
        "linked": "Vinculado à conta FINORA de {name}.\nEnvie \"ajuda\" para ver o menu.",
        "bad_code": "Código inválido ou expirado (30 minutos). Gere um novo no FINORA.",
        "already": "Esta conta LINE já está vinculada a outra conta FINORA. Desvincule-a primeiro.",
        "notif": "Notificações não lidas ({n})", "notif_none": "Nenhuma notificação não lida.",
        "inv": "Faturas em aberto ({n})", "inv_none": "Nenhuma fatura em aberto.",
        "inv_row": "・{number}  {amount}  vencimento {due}",
        "ec": "Contratos pendentes ({n})", "ec_none": "Nenhum contrato pendente.",
        "ec_row": "・{number}  {service}  {status}",
        "mt": "Próximas reuniões ({n})", "mt_none": "Nenhuma reunião agendada.",
        "mt_row": "・{when}  {title}",
        "assets": "Valor da carteira: {amount}\n({n} ativos, em {date})",
        "assets_none": "Nenhum ativo cadastrado.",
        "staff": "Equipe: {inv} faturas em aberto / {ec} contratos pendentes / {mt} reuniões futuras",
        "unknown": "Palavra não reconhecida. Envie \"ajuda\" para ver o menu.",
        "open": "Veja os detalhes no FINORA: {url}",
    },
}

NOTIF_TXT = {
    "ja": {"econtract_important_sent": "重要事項説明書が届きました", "econtract_agreement_sent": "契約書へのご署名のお願い",
           "econtract_recipient_signed": "相手方が署名しました", "econtract_renewal_notice": "契約更新期限のお知らせ",
           "invoice_issued": "請求書が発行されました", "payment_refunded": "返金が完了しました",
           "meeting_scheduled": "テレビ電話の予約", "meeting_reminder": "面談開始のリマインド", "meeting_cancelled": "面談が取り消されました",
           "minutes_approved": "議事録が公開されました", "comment_new": "新しいコメント", "contract_ended": "契約終了のお知らせ",
           "meeting_new": "面談の予約", "meeting_cancel": "面談の取消", "meeting_soon": "面談開始のリマインド",
           "client_data_updated": "顧客データが更新されました", "correction_request": "修正依頼", "correction_resolved": "修正依頼が対応されました",
           "consulting_request": "コンサルティング依頼", "task_due": "タスクの期限", "invoice_paid": "入金が確認されました",
           "payout_sent": "送金完了のお知らせ", "payment_confirmed": "入金が確認されました", "invoice_overdue": "支払期限を過ぎた請求",
           "meeting_minutes": "議事録のお知らせ"},
}
KEYS = {
    "notif": ("通知", "おしらせ", "お知らせ", "notice", "notification", "aviso", "avisos"),
    "inv": ("請求", "請求書", "invoice", "invoices", "billing", "fatura", "faturas"),
    "ec": ("契約", "けいやく", "contract", "contracts", "contrato", "contratos"),
    "mt": ("面談", "予約", "会議", "テレビ電話", "meeting", "meetings", "reuniao", "reunião"),
    "assets": ("資産", "しさん", "残高", "ポートフォリオ", "asset", "assets", "portfolio", "ativos", "carteira"),
    "menu": ("ヘルプ", "へるぷ", "メニュー", "menu", "help", "ajuda", "?", "？"),
}
EC_PENDING = {"IMPORTANT_INFO_SENT": {"ja": "重要事項の確認待ち", "en": "awaiting confirmation", "pt": "aguardando confirmação"},
              "CONTRACT_SENT": {"ja": "署名待ち", "en": "awaiting signature", "pt": "aguardando assinatura"},
              "FIRST_PARTY_SIGNED": {"ja": "相手方の署名待ち", "en": "awaiting counter-signature", "pt": "aguardando contra-assinatura"}}


def configured() -> bool:
    return bool(CHANNEL_SECRET and ACCESS_TOKEN)


def valid_signature(raw: bytes, received: str | None) -> bool:
    if not received:
        return False
    digest = hmac.new(CHANNEL_SECRET.encode(), raw, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), received)


async def _reply(reply_token: str, text: str):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{LINE_API}/message/reply",
                         headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
                         json={"replyToken": reply_token, "messages": [{"type": "text", "text": text[:4900]}]})
    if r.status_code >= 300:
        logger.error("LINE reply failed %s %s", r.status_code, r.text[:200])


def _x(lang):
    return TXT.get(lang if lang in TXT else "ja")


def _money(v):
    return f"¥{v:,.0f}"


def _when(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=9))).strftime("%m/%d %H:%M")
    except Exception:  # noqa: BLE001
        return iso or "—"


async def _notifications(user, x):
    rows = await db.notifications.find({"user_id": user["id"], "read": False}).sort("created_at", -1).to_list(10)
    if not rows:
        return x["notif_none"]
    names = NOTIF_TXT.get("ja", {})
    lines = [f"・{_when(r['created_at'])} {names.get(r['kind'], r['kind'])}" + (f"（{r['params']['label']}）" if (r.get("params") or {}).get("label") else "") for r in rows]
    return x["notif"].format(n=len(rows)) + "\n" + "\n".join(lines)


async def _invoices(user, x):
    q = {"tenant_id": user["tenant_id"], "status": {"$in": ["ISSUED", "PARTIALLY_PAID", "OVERDUE"]}}
    if user["role"] == "client":
        q["client_id"] = user.get("client_id")
    rows = await db.invoices.find(q).sort("due_date", 1).to_list(10)
    if not rows:
        return x["inv_none"]
    lines = [x["inv_row"].format(number=r["number"], amount=_money(r.get("balance") or r["total"]), due=r.get("due_date") or "—") for r in rows]
    return x["inv"].format(n=len(rows)) + "\n" + "\n".join(lines)


async def _contracts(user, x, lang):
    q = {"tenant_id": user["tenant_id"], "status": {"$in": list(EC_PENDING)}}
    if user["role"] == "client":
        q["client_id"] = user.get("client_id")
    rows = await db.econtracts.find(q).sort("created_at", -1).to_list(10)
    if not rows:
        return x["ec_none"]
    lines = [x["ec_row"].format(number=r.get("number") or "—", service=(r.get("terms") or {}).get("service_name") or "—",
                                status=EC_PENDING[r["status"]].get(lang, EC_PENDING[r["status"]]["ja"])) for r in rows]
    return x["ec"].format(n=len(rows)) + "\n" + "\n".join(lines)


async def _meetings(user, x):
    q = {"tenant_id": user["tenant_id"], "status": "scheduled", "scheduled_at": {"$gte": now_iso()}}
    if user["role"] == "client":
        q["client_id"] = user.get("client_id")
    else:
        q["consultant_id"] = user["id"]
    rows = await db.meetings.find(q).sort("scheduled_at", 1).to_list(10)
    if not rows:
        return x["mt_none"]
    return x["mt"].format(n=len(rows)) + "\n" + "\n".join(x["mt_row"].format(when=_when(r["scheduled_at"]), title=r.get("title") or "—") for r in rows)


async def _assets(user, x):
    cid = user.get("client_id")
    if not cid:
        return x["assets_none"]
    rows = await db.assets.find({"tenant_id": user["tenant_id"], "client_id": cid}).to_list(500)
    if not rows:
        return x["assets_none"]
    total = 0.0
    for a in rows:
        unit = a.get("price_unit") or 1
        qty, price = a.get("quantity") or 0, a.get("current_price") or 0
        total += (qty * price / unit) if qty and price else (a.get("current_value") or 0)
    return x["assets"].format(amount=_money(total), n=len(rows), date=datetime.now(timezone(timedelta(hours=9))).date().isoformat())


async def _answer(user, text, lang):
    x, low = _x(lang), text.strip().lower()
    for key, words in KEYS.items():
        if low in words or any(w in low for w in words):
            if key == "menu":
                return x["menu"]
            if key == "notif":
                return await _notifications(user, x)
            if key == "inv":
                return await _invoices(user, x)
            if key == "ec":
                return await _contracts(user, x, lang)
            if key == "mt":
                return await _meetings(user, x)
            if key == "assets":
                return await _assets(user, x) if user["role"] == "client" else await _staff(user, x)
    return x["unknown"]


async def _staff(user, x):
    inv = await db.invoices.count_documents({"tenant_id": user["tenant_id"], "status": {"$in": ["ISSUED", "PARTIALLY_PAID", "OVERDUE"]}})
    ec = await db.econtracts.count_documents({"tenant_id": user["tenant_id"], "status": {"$in": list(EC_PENDING)}})
    mt = await db.meetings.count_documents({"tenant_id": user["tenant_id"], "consultant_id": user["id"], "status": "scheduled", "scheduled_at": {"$gte": now_iso()}})
    return x["staff"].format(inv=inv, ec=ec, mt=mt)


async def _try_link(line_user_id, code, lang):
    x = _x(lang)
    doc = await db.line_link_codes.find_one({"code": code, "used": False})
    if not doc or doc["expires_at"] < now_iso():
        return x["bad_code"]
    owner = await db.users.find_one({"line_user_id": line_user_id})
    if owner and owner["id"] != doc["user_id"]:
        return x["already"]
    u = await db.users.find_one({"id": doc["user_id"]})
    if not u:
        return x["bad_code"]
    await db.users.update_one({"id": u["id"]}, {"$set": {"line_user_id": line_user_id, "line_linked_at": now_iso()}})
    await db.line_link_codes.update_one({"id": doc["id"]}, {"$set": {"used": True, "used_at": now_iso()}})
    return _x(u.get("lang") or lang)["linked"].format(name=u.get("name") or u["email"])


async def _handle(event):
    if event.get("type") != "message" or (event.get("message") or {}).get("type") != "text":
        return
    token, line_user_id = event.get("replyToken"), (event.get("source") or {}).get("userId")
    if not token or not line_user_id:
        return
    text = (event["message"].get("text") or "").strip()
    user = await db.users.find_one({"line_user_id": line_user_id, "active": True})
    code = "".join(ch for ch in text if ch.isdigit())
    if not user:
        await _reply(token, await _try_link(line_user_id, code, "ja") if len(code) == 6 else _x("ja")["need_link"])
        return
    lang = user.get("lang") or "ja"
    await _reply(token, await _answer(user, text, lang))


@router.post("/webhook")
async def webhook(request: Request, x_line_signature: str | None = Header(default=None)):
    raw = await request.body()
    if not configured():
        raise HTTPException(503, "LINE is not configured")
    if not valid_signature(raw, x_line_signature):
        raise HTTPException(400, "invalid signature")
    body = await request.json()
    for event in body.get("events", []):
        eid = event.get("webhookEventId")
        if eid:
            try:
                await db.line_events.insert_one({"id": new_id(), "webhook_event_id": eid, "at": now_iso()})
            except Exception:  # noqa: BLE001
                continue
        try:
            await _handle(event)
        except Exception as e:  # noqa: BLE001
            logger.error("LINE event failed: %s", e)
    return {"ok": True}


@router.get("/status")
async def status(user=Depends(current)):
    return {"configured": configured(), "bot_id": BOT_BASIC_ID,
            "linked": bool(user.get("line_user_id")), "linked_at": user.get("line_linked_at")}


@router.post("/link-code")
async def link_code(request: Request, user=Depends(current)):
    if not configured():
        raise HTTPException(503, "LINE is not configured")
    await db.line_link_codes.update_many({"user_id": user["id"], "used": False}, {"$set": {"used": True}})
    code = f"{random.randint(0, 999999):06d}"
    exp = (datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MIN)).isoformat()
    await db.line_link_codes.insert_one({"id": new_id(), "user_id": user["id"], "tenant_id": user["tenant_id"],
                                         "code": code, "used": False, "expires_at": exp, "created_at": now_iso()})
    await audit(user, "line_link_code", "users", user["id"], request=request)
    return {"code": code, "expires_at": exp, "bot_id": BOT_BASIC_ID, "ttl_minutes": CODE_TTL_MIN}


@router.delete("/link")
async def unlink(request: Request, user=Depends(current)):
    await db.users.update_one({"id": user["id"]}, {"$unset": {"line_user_id": "", "line_linked_at": ""}})
    await audit(user, "line_unlink", "users", user["id"], request=request)
    return {"ok": True}
