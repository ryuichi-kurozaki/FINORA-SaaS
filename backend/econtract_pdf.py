"""Final (immutable) PDF rendering for e-contract documents; IPA Gothic covers ja / en / pt."""
import base64
import io
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
