"""E-contract review/sign requests via email (Emergent managed) and the server's shared WhatsApp service."""
import logging
import os
import re
from datetime import datetime, timezone
from html import escape

import httpx

from core import db, decrypt, new_id
from email_service import APP_URL, EMAIL_FROM_NAME, send_email

logger = logging.getLogger(__name__)
WA_URL = os.environ["WHATSAPP_SERVICE_URL"].rstrip("/")
KINDS = ("econtract_important_sent", "econtract_agreement_sent", "econtract_recipient_signed")


def wa_digits(p):
    """Digits-only WhatsApp number; a domestic JP number (leading single 0) gets country code 81."""
    d = re.sub(r"\D", "", p or "")
    return "81" + d[1:] if d.startswith("0") and not d.startswith("00") else d.lstrip("0") or None

TXT = {
    "ja": {"econtract_important_sent": ("【FINORA】重要事項説明書のご確認のお願い（{number}）", "{issuer}から「{service}」の重要事項説明書が届きました。内容をご確認のうえ、確認・同意をお願いいたします。"),
           "econtract_agreement_sent": ("【FINORA】契約書へのご署名のお願い（{number}）", "{issuer}から「{service}」の契約書が届きました。内容をご確認のうえ、電子署名をお願いいたします。"),
           "econtract_recipient_signed": ("【FINORA】相手方が署名しました（{number}）", "「{service}」の契約書に相手方が電子署名しました。内容をご確認のうえ、電子署名して契約を成立させてください。"),
           "hello": "{name} 様", "cta": "FINORAで確認・署名する", "login": "リンクを開いた後、FINORAにログインしてください。",
           "footer": "このメールは {brand} から自動送信されています。FINORAがメールやWhatsAppでパスワードをお尋ねすることはありません。"},
    "en": {"econtract_important_sent": ("[FINORA] Please review the important information statement ({number})", "{issuer} has sent you the important information statement for \"{service}\". Please review it and confirm."),
           "econtract_agreement_sent": ("[FINORA] Please sign the agreement ({number})", "{issuer} has sent you the agreement for \"{service}\". Please review it and sign electronically."),
           "econtract_recipient_signed": ("[FINORA] The other party has signed ({number})", "The other party has signed the agreement for \"{service}\". Please review and sign to execute the contract."),
           "hello": "Dear {name},", "cta": "Review and sign in FINORA", "login": "After opening the link, please log in to FINORA.",
           "footer": "This message was sent automatically by {brand}. FINORA never asks for your password by email or WhatsApp."},
    "pt": {"econtract_important_sent": ("[FINORA] Revise a declaração de informações importantes ({number})", "{issuer} enviou a declaração de informações importantes de \"{service}\". Revise e confirme, por favor."),
           "econtract_agreement_sent": ("[FINORA] Assine o contrato ({number})", "{issuer} enviou o contrato de \"{service}\". Revise e assine eletronicamente, por favor."),
           "econtract_recipient_signed": ("[FINORA] A outra parte assinou ({number})", "A outra parte assinou o contrato de \"{service}\". Revise e assine para concluir o contrato."),
           "hello": "Olá, {name}", "cta": "Revisar e assinar no FINORA", "login": "Depois de abrir o link, faça login no FINORA.",
           "footer": "Mensagem enviada automaticamente por {brand}. A FINORA nunca pede sua senha por e-mail ou WhatsApp."},
}


RENEW = {
    "ja": {True: ("【FINORA】契約更新日のお知らせ（{number}）", "「{service}」の契約は {date} に更新日を迎えます（残り{days}日）。同一条件で自動更新されます。条件の変更や解約をご希望の場合は、更新日までに相手方とご相談ください。"),
           False: ("【FINORA】契約満了のお知らせ（{number}）", "「{service}」の契約は {date} に期間満了となります（残り{days}日）。自動更新はされません。継続をご希望の場合は、満了日までに再契約をご検討ください。"),
           "cta": "FINORAで契約を確認する"},
    "en": {True: ("[FINORA] Contract renewal notice ({number})", "Your \"{service}\" contract reaches its renewal date on {date} ({days} days left). It will renew automatically on the same terms. If you wish to change or cancel it, please contact the other party before the renewal date."),
           False: ("[FINORA] Contract expiry notice ({number})", "Your \"{service}\" contract expires on {date} ({days} days left). It will not renew automatically. If you wish to continue, please consider a new contract before the expiry date."),
           "cta": "View the contract in FINORA"},
    "pt": {True: ("[FINORA] Aviso de renovação do contrato ({number})", "O contrato \"{service}\" chega à data de renovação em {date} (faltam {days} dias). Ele será renovado automaticamente nas mesmas condições. Para alterar ou cancelar, fale com a outra parte antes da data de renovação."),
           False: ("[FINORA] Aviso de término do contrato ({number})", "O contrato \"{service}\" termina em {date} (faltam {days} dias). Ele não será renovado automaticamente. Para continuar, considere um novo contrato antes do término."),
           "cta": "Ver o contrato no FINORA"},
}


def _html(x, name, msg, link, cta=None):
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:24px 0"><tr><td align="center">'
            '<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;font-family:Arial,Helvetica,sans-serif">'
            '<tr><td style="background:#071A2B;padding:20px 28px;border-radius:12px 12px 0 0;color:#ffffff;font-size:20px;font-weight:bold;letter-spacing:2px">FIN<span style="color:#00A878">ORA</span></td></tr>'
            f'<tr><td style="padding:28px"><p style="margin:0 0 12px;color:#071A2B;font-size:15px">{escape(x["hello"].format(name=name))}</p>'
            f'<p style="margin:0 0 20px;color:#334155;font-size:14px;line-height:1.7">{escape(msg)}</p>'
            f'<a href="{escape(link)}" style="display:inline-block;background:#00A878;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:8px;font-size:14px;font-weight:bold">{escape(cta or x["cta"])}</a>'
            f'<p style="margin:16px 0 0;color:#64748b;font-size:12px">{escape(x["login"])}</p>'
            f'<p style="margin:28px 0 0;color:#94a3b8;font-size:11px;line-height:1.6">{escape(x["footer"].format(brand=EMAIL_FROM_NAME))}</p>'
            '</td></tr></table></td></tr></table>')


async def _log(c, u, channel, to, kind, status, detail=""):
    await db.message_log.insert_one({"id": new_id(), "tenant_id": c["tenant_id"], "contract_id": c["id"], "user_id": u["id"], "channel": channel,
                                     "to": to, "kind": kind, "status": status, "detail": str(detail)[:300], "at": datetime.now(timezone.utc).isoformat()})


async def send_sign_request(user_id, c, kind, issuer_name):
    u = await db.users.find_one({"id": user_id})
    if not u or kind not in KINDS:
        return
    x = TXT.get(u.get("lang")) or TXT.get(c.get("lang")) or TXT["ja"]
    subject, body = (s.format(number=c["number"], issuer=issuer_name, service=c["terms"]["service_name"]) for s in x[kind])
    await _deliver(c, u, kind, x, subject, body, x["cta"])


async def send_renewal_notice(user_id, c, renew_date, days):
    u = await db.users.find_one({"id": user_id})
    if not u:
        return
    lang = u.get("lang") if u.get("lang") in TXT else c.get("lang") if c.get("lang") in TXT else "ja"
    auto = bool(c["terms"].get("auto_renew"))
    subject, body = (s.format(number=c["number"], service=c["terms"]["service_name"], date=renew_date, days=days) for s in RENEW[lang][auto])
    await _deliver(c, u, "econtract_renewal_notice", TXT[lang], subject, body, RENEW[lang]["cta"])


async def _deliver(c, u, kind, x, subject, body, cta):
    link = f"{APP_URL}/econtracts/{c['id']}"
    try:
        await send_email(to=u["email"], subject=subject, html=_html(x, u.get("name") or u["email"], body, link, cta))
        await _log(c, u, "EMAIL", u["email"], kind, "SENT")
    except Exception as e:
        logger.error("sign request email failed %s: %s", c["number"], e)
        await _log(c, u, "EMAIL", u["email"], kind, "FAILED", e)
    phone, opted = u.get("whatsapp_phone"), u.get("whatsapp_opt_in")
    if not phone and u.get("role") == "client" and u.get("client_id"):
        cl = await db.clients.find_one({"id": u["client_id"]}, {"whatsapp": 1}) or {}
        phone = wa_digits(decrypt(cl["whatsapp"])) if cl.get("whatsapp") else None
        opted = bool(phone)
    if not (WA_URL and phone and opted):
        return
    try:
        async with httpx.AsyncClient(timeout=20) as h:
            r = await h.post(f"{WA_URL}/send", json={"phone": phone, "message": f"{subject}\n\n{body}\n\n{cta}: {link}\n{x['login']}"})
        await _log(c, u, "WHATSAPP", phone, kind, "SENT" if r.status_code == 200 else "FAILED", "" if r.status_code == 200 else r.text)
    except Exception as e:
        logger.error("sign request whatsapp failed %s: %s", c["number"], e)
        await _log(c, u, "WHATSAPP", phone, kind, "FAILED", e)
