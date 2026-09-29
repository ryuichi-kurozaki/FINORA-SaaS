"""Final (immutable) PDF rendering for e-contract documents; IPA Gothic covers ja / en / pt."""
import base64
import io
from datetime import datetime, timezone
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

pdfmetrics.registerFont(TTFont("IPAG", str(Path(__file__).parent / "fonts" / "ipag.ttf")))
S = {n: ParagraphStyle(n, fontName="IPAG", fontSize=z, leading=z * 1.55, spaceAfter=a, textColor=colors.HexColor(c))
     for n, z, a, c in (("h1", 16, 4, "#071A2B"), ("meta", 8, 1, "#64748B"), ("h2", 10.5, 2, "#0B6E4F"), ("p", 9, 6, "#0F172A"))}
L = {"ja": ("契約番号", "書類番号", "版", "改ざん検知(SHA-256)", "署名", "署名者", "署名日時", "契約成立日時"),
     "en": ("Contract No.", "Document No.", "Version", "Integrity (SHA-256)", "Signatures", "Signer", "Signed at", "Executed at"),
     "pt": ("Contrato nº", "Documento nº", "Versão", "Integridade (SHA-256)", "Assinaturas", "Signatário", "Assinado em", "Celebrado em")}


def _p(txt, st="p"):
    return Paragraph(escape(str(txt)).replace("\n", "<br/>"), S[st])


def render(doc, contract, signs):
    """doc: econtract_docs record; signs: list of SIGN acts (for the agreement) or CONFIRM acts (for the statement)."""
    lab = L.get(doc["lang"], L["ja"])
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=doc["title"], author="FINORA")
    els = [_p(doc["title"], "h1"),
           _p(f"{lab[0]}: {contract['number']}  /  {lab[1]}: {doc['number']}  /  {lab[2]}: {doc['version']}", "meta"),
           _p(f"{lab[3]}: {doc['hash']}", "meta"), Spacer(1, 6)]
    for s in doc["sections"]:
        els += [_p(s["title"], "h2"), _p(s["body"])]
    els += [Spacer(1, 8), _p(lab[4], "h2")]
    for a in signs:
        img = None
        if a.get("signature_png", "").startswith("data:image/png;base64,"):
            img = Image(io.BytesIO(base64.b64decode(a["signature_png"].split(",", 1)[1])), width=45 * mm, height=16 * mm)
        info = _p(f"{a.get('party_label', '')}\n{lab[5]}: {a.get('signer_name') or a.get('user_email')}\n{lab[6]}: {a['at']}\nIP: {a.get('ip')}", "meta")
        t = Table([[info, img or ""]], colWidths=[110 * mm, 55 * mm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        els += [t, Spacer(1, 4)]
    if contract.get("activated_at"):
        els.append(_p(f"{lab[7]}: {contract['activated_at']}", "meta"))
    pdf.build(els)
    return buf.getvalue()



CERT = {
    "ja": {"title": "契約締結証明書", "no": "証明書番号", "issued": "発行日時", "note": "本証明書は、下記の電子契約が FINORA 上で締結されたことを証明するものです。各書類のSHA-256値により、書類の改ざんがないことを検証できます。",
           "rows": ("契約番号", "契約種別", "サービス内容", "料金", "契約期間", "契約成立日時", "契約状態", "終了日", "甲（発行者）", "乙（相手方）",
                    "重要事項説明書", "契約書", "重要事項説明書のSHA-256", "契約書のSHA-256"), "signs": "署名記録", "issuer_label": "発行者"},
    "en": {"title": "Certificate of Contract Execution", "no": "Certificate No.", "issued": "Issued at", "note": "This certificate attests that the contract below was executed on FINORA. The SHA-256 values allow verification that the documents have not been altered.",
           "rows": ("Contract No.", "Contract type", "Service", "Fees", "Term", "Executed at", "Status", "End date", "Issuer", "Counterparty",
                    "Important information statement", "Agreement", "Statement SHA-256", "Agreement SHA-256"), "signs": "Signature records", "issuer_label": "Issued by"},
    "pt": {"title": "Certificado de Celebração de Contrato", "no": "Certificado nº", "issued": "Emitido em", "note": "Este certificado atesta que o contrato abaixo foi celebrado no FINORA. Os valores SHA-256 permitem verificar que os documentos não foram alterados.",
           "rows": ("Contrato nº", "Tipo de contrato", "Serviço", "Honorários", "Vigência", "Celebrado em", "Situação", "Data de término", "Emitente", "Contraparte",
                    "Declaração de informações importantes", "Contrato", "SHA-256 da declaração", "SHA-256 do contrato"), "signs": "Registros de assinatura", "issuer_label": "Emitido por"},
}


def render_certificate(lang, cert_no, values, signs, issuer_block):
    """One-page proof that the contract was executed; values follows CERT[lang]['rows'] order."""
    x = CERT.get(lang, CERT["ja"])
    lab = L.get(lang, L["ja"])
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=x["title"], author="FINORA")
    els = [_p(x["title"], "h1"), _p(f"{x['no']}: {cert_no}  /  {x['issued']}: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}", "meta"),
           Spacer(1, 4), _p(x["note"], "p"), Spacer(1, 4)]
    rows = [[_p(k, "meta"), _p(v or "—", "p")] for k, v in zip(x["rows"], values)]
    tbl = Table(rows, colWidths=[52 * mm, 113 * mm])
    tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    els += [tbl, Spacer(1, 10), _p(x["signs"], "h2")]
    for a in signs:
        img = None
        if a.get("signature_png", "").startswith("data:image/png;base64,"):
            img = Image(io.BytesIO(base64.b64decode(a["signature_png"].split(",", 1)[1])), width=45 * mm, height=16 * mm)
        info = _p(f"{a.get('party_label', '')}\n{lab[5]}: {a.get('signer_name') or a.get('user_email')}\n{lab[6]}: {a['at']}\nIP: {a.get('ip')}", "meta")
        t = Table([[info, img or ""]], colWidths=[110 * mm, 55 * mm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        els += [t, Spacer(1, 4)]
    els += [Spacer(1, 10), _p(f"{x['issuer_label']}:\n{issuer_block}", "meta")]
    pdf.build(els)
    return buf.getvalue()
