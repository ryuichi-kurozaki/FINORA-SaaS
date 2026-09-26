"""Transactional email via the server's own SMTP (Postfix + DKIM, no per-message cost). EMAIL_TRANSPORT=log only records (preview)."""
import asyncio
import ipaddress
import logging
import os
import re
import smtplib
from datetime import datetime
from email.header import Header
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from core import db, new_id, now_iso

logger = logging.getLogger(__name__)
EMAIL_TRANSPORT = os.environ["EMAIL_TRANSPORT"]
EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_REPLY_TO = os.environ["EMAIL_REPLY_TO"]
SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = int(os.environ["SMTP_PORT"])
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
APP_URL = os.environ["PUBLIC_APP_URL"].rstrip("/")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


async def _record(to, subject, kind, message_id, status, detail=""):
    at = now_iso()
    await db.email_log.insert_one({"id": new_id(), "to": to, "subject": subject, "kind": kind, "message_id": message_id.strip("<>"),
                                   "queue_id": None, "status": status, "detail": str(detail)[:300], "at": at, "updated_at": at})


async def send_email(*, to: str, subject: str, html: str, reply_to: str | None = None, kind: str = "other") -> str | None:
    _assert_safe_email(subject, html)
    msg = EmailMessage()
    msg["From"] = formataddr((str(Header(EMAIL_FROM_NAME, "utf-8")), EMAIL_FROM))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Reply-To"] = reply_to or EMAIL_REPLY_TO
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=EMAIL_FROM.split("@")[-1])
    msg.set_content(re.sub(r"<[^>]+>", " ", html))
    msg.add_alternative(html, subtype="html")
    if EMAIL_TRANSPORT == "log":
        logger.info("email (log transport, not sent) to=%s subject=%s", to, subject)
        await _record(to, subject, kind, msg["Message-ID"], "logged")
        return msg["Message-ID"]

    def _send():
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.send_message(msg)
    try:
        await asyncio.to_thread(_send)
    except Exception as e:
        await _record(to, subject, kind, msg["Message-ID"], "failed", e)
        raise
    await _record(to, subject, kind, msg["Message-ID"], "queued")
    return msg["Message-ID"]


TEXT = {
    "ja": {"subject": "【FINORA】返金のお知らせ（{number}）", "hello": "{name} 様",
           "intro": "{company} からのご請求について、カードへの返金手続きが完了しました。",
           "number": "請求書番号", "amount": "返金額", "date": "返金日",
           "note": "返金はご利用のカード会社を通じて行われます。明細に反映されるまで数日〜2週間ほどかかる場合があります。",
           "cta": "FINORAで請求を確認する", "footer": "このメールは {brand} から自動送信されています。{brand} がメールでパスワードやカード情報をお尋ねすることはありません。"},
    "en": {"subject": "[FINORA] Refund notice ({number})", "hello": "Dear {name},",
           "intro": "A refund to your card has been processed for your invoice from {company}.",
           "number": "Invoice no.", "amount": "Refund amount", "date": "Refund date",
           "note": "The refund is returned through your card issuer and may take from a few days up to 2 weeks to appear on your statement.",
           "cta": "View your invoices on FINORA", "footer": "This email was sent automatically by {brand}. {brand} will never ask for your password or card details by email."},
    "pt": {"subject": "[FINORA] Aviso de reembolso ({number})", "hello": "Prezado(a) {name},",
           "intro": "O reembolso no seu cartão referente à fatura de {company} foi processado.",
           "number": "Nº da fatura", "amount": "Valor reembolsado", "date": "Data do reembolso",
           "note": "O reembolso é feito pela administradora do cartão e pode levar de alguns dias até 2 semanas para aparecer na fatura.",
           "cta": "Ver faturas no FINORA", "footer": "Este e-mail foi enviado automaticamente pelo {brand}. O {brand} nunca solicita senha ou dados do cartão por e-mail."},
}


def _row(label, value):
    return (f'<tr><td style="padding:8px 0;color:#64748b;font-size:13px;width:40%">{escape(label)}</td>'
            f'<td style="padding:8px 0;color:#071A2B;font-size:14px;font-weight:bold">{escape(value)}</td></tr>')


def refund_html(lang, name, company, number, amount, day):
    x = TEXT.get(lang) or TEXT["ja"]
    subject = x["subject"].format(number=number)
    html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:24px 0">'
        '<tr><td align="center"><table role="presentation" width="560" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border-radius:12px;font-family:Arial,Helvetica,sans-serif">'
        f'<tr><td style="background:#071A2B;padding:20px 28px;border-radius:12px 12px 0 0;color:#ffffff;font-size:20px;font-weight:bold;letter-spacing:2px">FIN<span style="color:#00A878">ORA</span></td></tr>'
        f'<tr><td style="padding:28px">'
        f'<p style="margin:0 0 12px;color:#071A2B;font-size:15px">{escape(x["hello"].format(name=name))}</p>'
        f'<p style="margin:0 0 20px;color:#334155;font-size:14px;line-height:1.7">{escape(x["intro"].format(company=company))}</p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;margin-bottom:20px">'
        f'{_row(x["number"], number)}{_row(x["amount"], f"¥{amount:,.0f}")}{_row(x["date"], day)}</table>'
        f'<p style="margin:0 0 24px;color:#64748b;font-size:13px;line-height:1.7">{escape(x["note"])}</p>'
        f'<a href="{escape(APP_URL)}/billing" style="display:inline-block;background:#00A878;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:8px;font-size:14px;font-weight:bold">{escape(x["cta"])}</a>'
        f'<p style="margin:28px 0 0;color:#94a3b8;font-size:11px;line-height:1.6">{escape(x["footer"].format(brand=EMAIL_FROM_NAME))}</p>'
        '</td></tr></table></td></tr></table>')
    return subject, html


async def send_refund_receipt(tenant_id, inv, amount):
    """Emails a refund receipt to the invoiced customer's login accounts; never raises."""
    try:
        t = await db.tenants.find_one({"id": tenant_id}) or {}
        bp = t.get("billing_profile") or {}
        company = bp.get("company_name") or t.get("name") or EMAIL_FROM_NAME
        day = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        users = await db.users.find({"tenant_id": tenant_id, "client_id": inv["client_id"], "role": "client", "active": True}).to_list(20)
        for u in users:
            subject, html = refund_html(u.get("lang") or "ja", u.get("name") or u["email"], company, inv["number"], amount, day)
            eid = await send_email(to=u["email"], subject=subject, html=html, reply_to=bp.get("email") or None, kind="refund")
            logger.info("refund receipt sent to %s (%s) id=%s", u["email"], inv["number"], eid)
    except Exception as e:
        logger.error("refund receipt email failed for %s: %s", inv.get("number"), e)
