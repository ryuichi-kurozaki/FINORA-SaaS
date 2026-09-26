"""Invoice issued → email + WhatsApp to the client (card-pay link when the client's consultant accepts cards)."""
from core import db, decrypt
from email_service import send_email
from payouts import card_clients
from sign_notify import APP_URL, TXT, _html, wa_send

INV = {
    "ja": ("【{tenant}】ご請求書発行のお知らせ（{number}）", "{tenant}より請求書 {number} を発行しました。\nご請求金額：{amount}\nお支払期限：{due}",
           "FINORAにログインし、請求画面の「カードで支払う」からクレジットカードでお支払いいただけます。", "お振込先は請求書に記載しています。FINORAにログインしてご確認ください。", "請求書を確認する", "{name} 様"),
    "en": ("[{tenant}] New invoice issued ({number})", "{tenant} has issued invoice {number}.\nAmount due: {amount}\nDue date: {due}",
           "Log in to FINORA and use \"Pay by card\" on the billing page to pay by credit card.", "Bank transfer details are on the invoice. Please log in to FINORA to view it.", "View invoice", "Dear {name},"),
    "pt": ("[{tenant}] Nova fatura emitida ({number})", "{tenant} emitiu a fatura {number}.\nValor: {amount}\nVencimento: {due}",
           "Entre na FINORA e use \"Pagar com cartão\" na página de cobrança para pagar com cartão de crédito.", "Os dados para transferência estão na fatura. Entre na FINORA para consultá-la.", "Ver fatura", "Prezado(a) {name},"),
}


def _merge(a, b):
    return "SENT" if "SENT" in (a, b) else "FAILED" if "FAILED" in (a, b) else "SKIPPED"


async def send_invoice_issued(inv, tenant_id):
    t = await db.tenants.find_one({"id": tenant_id}, {"name": 1}) or {}
    cl = await db.clients.find_one({"id": inv["client_id"]}, {"name": 1, "email": 1, "whatsapp": 1}) or {}
    client_wa = decrypt(cl["whatsapp"]) if cl.get("whatsapp") else None
    card = inv["client_id"] in await card_clients(tenant_id)
    users = await db.users.find({"tenant_id": tenant_id, "client_id": inv["client_id"], "role": "client", "active": True}).to_list(20)
    targets = [(u.get("lang"), u.get("name") or cl.get("name"), u["email"], u.get("whatsapp_phone") if u.get("whatsapp_opt_in") and u.get("whatsapp_phone") else client_wa) for u in users] \
        or [(None, cl.get("name"), cl.get("email"), client_wa)]
    out, sent_wa = {"email": "SKIPPED", "whatsapp": "SKIPPED"}, set()
    for lang, name, email, phone in targets:
        lang = lang if lang in INV else "ja"
        subj, body, card_txt, bank_txt, cta, hello = INV[lang]
        fmt = {"tenant": t.get("name") or "FINORA", "number": inv["number"], "amount": f"¥{inv['total']:,.0f}", "due": inv.get("due_date") or "—"}
        subject, msg = subj.format(**fmt), body.format(**fmt) + "\n\n" + (card_txt if card else bank_txt)
        link = f"{APP_URL}/billing"
        if email:
            try:
                await send_email(to=email, subject=subject, html=_html({**TXT[lang], "hello": hello, "login": ""}, name or email, msg, link, cta))
                out["email"] = _merge(out["email"], "SENT")
            except Exception:  # noqa: BLE001
                out["email"] = _merge(out["email"], "FAILED")
        if phone and phone not in sent_wa:
            sent_wa.add(phone)
            out["whatsapp"] = _merge(out["whatsapp"], await wa_send(phone, f"{subject}\n\n{hello.format(name=name or '')}\n{msg}\n\n{cta}: {link}"))
    return out
