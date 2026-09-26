"""Client invitation delivery: email (Emergent managed) + WhatsApp (shared local service)."""
import logging

import httpx

from email_service import APP_URL, send_email
from sign_notify import TXT, WA_URL, _html, wa_digits

logger = logging.getLogger(__name__)

INV = {
    "ja": ("【FINORA】{tenant}からのご招待", "{inviter}（{tenant}）から、資産管理サービスFINORAへのご招待が届きました。下のリンクからパスワードを設定して、ご利用を開始してください（有効期限：7日間）。", "招待を受けてアカウントを作成する", "{name} 様"),
    "en": ("[FINORA] Invitation from {tenant}", "{inviter} ({tenant}) has invited you to FINORA, a wealth management service. Please open the link below to set your password and get started (valid for 7 days).", "Accept the invitation", "Dear {name},"),
    "pt": ("[FINORA] Convite de {tenant}", "{inviter} ({tenant}) convidou você para a FINORA, um serviço de gestão patrimonial. Abra o link abaixo para definir sua senha e começar (válido por 7 dias).", "Aceitar o convite", "Olá, {name}"),
}


async def send_invite(inv, token, lang, tenant_name, client_name, whatsapp):
    """Returns delivery status per channel; never raises."""
    lang = lang if lang in INV else "ja"
    subject, body, cta, hello = INV[lang]
    subject, body = subject.format(tenant=tenant_name), body.format(tenant=tenant_name, inviter=inv.get("invited_by_name") or tenant_name)
    link = f"{APP_URL}/invite/{token}"
    x = {**TXT[lang], "hello": hello, "login": ""}
    out = {"email": "FAILED", "whatsapp": "SKIPPED"}
    try:
        await send_email(to=inv["email"], subject=subject, html=_html(x, client_name or inv["email"], body, link, cta))
        out["email"] = "SENT"
    except Exception as e:  # noqa: BLE001
        logger.error("invite email failed %s: %s", inv["email"], e)
    phone = wa_digits(whatsapp)
    if phone and WA_URL:
        try:
            async with httpx.AsyncClient(timeout=20) as h:
                r = await h.post(f"{WA_URL}/send", json={"phone": phone, "message": f"{subject}\n\n{body}\n\n{cta}: {link}"})
            out["whatsapp"] = "SENT" if r.status_code == 200 else "FAILED"
        except Exception as e:  # noqa: BLE001
            logger.error("invite whatsapp failed %s: %s", phone, e)
            out["whatsapp"] = "FAILED"
    return out
