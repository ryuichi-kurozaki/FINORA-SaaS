"""Public corporate website CMS: settings (company info etc.), items (service/news/faq/history), image uploads. Localized fields are {ja,en,pt}."""
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core import audit, clean, db, new_id, now_iso, platform_admin

router = APIRouter(prefix="/api")
UPLOAD_DIR = Path(os.environ["SITE_UPLOAD_DIR"])
KINDS = ("service", "news", "faq", "history")
NEWS_CATS = ("notice", "press", "media", "event")
IMG_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}


def loc(v, lang):
    return (v.get(lang) or v.get("ja") or "") if isinstance(v, dict) else v


def _resolve(d, lang):
    return {k: loc(v, lang) for k, v in d.items()}


def _item(i, lang):
    return {"id": i["id"], "kind": i["kind"], "date": i.get("date"), "category": i.get("category"), "image": i.get("image"),
            "title": loc(i.get("title", {}), lang), "body": loc(i.get("body", {}), lang), "order": i.get("order", 0)}


async def _items(kind, lang, published=True, limit=500):
    q = {"kind": kind, **({"published": True} if published else {})}
    sort = [("date", -1)] if kind == "news" else [("order", 1), ("date", 1)]
    return [_item(i, lang) for i in await db.site_items.find(q).sort(sort).to_list(limit)]


@router.get("/public/site")
async def public_site(lang: str = "ja"):
    s = await db.site_settings.find_one({"id": "main"}) or {"data": {}}
    return {"settings": _resolve(s["data"], lang), "services": await _items("service", lang), "faqs": await _items("faq", lang),
            "history": await _items("history", lang), "news": await _items("news", lang, limit=5)}


@router.get("/public/site/news")
async def public_news(lang: str = "ja", category: Optional[str] = None):
    items = await _items("news", lang)
    return [i for i in items if not category or i["category"] == category]


@router.get("/public/site/news/{nid}")
async def public_news_item(nid: str, lang: str = "ja"):
    i = await db.site_items.find_one({"id": nid, "kind": "news", "published": True})
    if not i:
        raise HTTPException(404, "Not found")
    return _item(i, lang)


@router.get("/public/site/files/{name}")
async def site_file(name: str):
    p = UPLOAD_DIR / Path(name).name
    if not p.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/platform/site")
async def admin_site(user=Depends(platform_admin)):
    s = await db.site_settings.find_one({"id": "main"}) or {"data": {}}
    return {"settings": s["data"], "items": [clean(i) for i in await db.site_items.find().sort([("kind", 1), ("order", 1), ("date", -1)]).to_list(2000)]}


class SettingsIn(BaseModel):
    data: dict


@router.put("/platform/site/settings")
async def save_settings(body: SettingsIn, request: Request, user=Depends(platform_admin)):
    await db.site_settings.update_one({"id": "main"}, {"$set": {"data": body.data, "updated_at": now_iso(), "updated_by": user["id"]}}, upsert=True)
    await audit(user, "update", "site_settings", "main", request=request, label="site settings")
    return {"ok": True}


class ItemIn(BaseModel):
    kind: str = Field(pattern="^(service|news|faq|history)$")
    title: dict = {}
    body: dict = {}
    date: Optional[str] = None
    category: Optional[str] = None
    image: Optional[str] = None
    order: int = 0
    published: bool = True


def _check(body):
    if not (body.title.get("ja") or "").strip():
        raise HTTPException(422, "Japanese title is required")
    if body.kind == "news" and body.category not in NEWS_CATS:
        raise HTTPException(422, "Invalid category")


@router.post("/platform/site/items")
async def create_item(body: ItemIn, request: Request, user=Depends(platform_admin)):
    _check(body)
    doc = {"id": new_id(), **body.model_dump(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.site_items.insert_one(doc)
    await audit(user, "create", "site_items", doc["id"], request=request, label=body.title.get("ja"))
    return clean(doc)


@router.put("/platform/site/items/{iid}")
async def update_item(iid: str, body: ItemIn, request: Request, user=Depends(platform_admin)):
    _check(body)
    r = await db.site_items.update_one({"id": iid}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await audit(user, "update", "site_items", iid, request=request, label=body.title.get("ja"))
    return {"ok": True}


@router.delete("/platform/site/items/{iid}")
async def delete_item(iid: str, request: Request, user=Depends(platform_admin)):
    await db.site_items.delete_one({"id": iid})
    await audit(user, "delete", "site_items", iid, request=request)
    return {"ok": True}


@router.post("/platform/site/upload")
async def upload(file: UploadFile = File(...), user=Depends(platform_admin)):
    ext = IMG_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(422, "Only PNG, JPEG, WebP or GIF images are allowed")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "File is too large (max 5MB)")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/api/public/site/files/{name}"}


def L(ja, en, pt):
    return {"ja": ja, "en": en, "pt": pt}


async def seed_site():
    """Placeholder content (admin replaces it) — only when nothing exists yet."""
    if await db.site_settings.find_one({"id": "main"}):
        return
    await db.site_settings.insert_one({"id": "main", "created_at": now_iso(), "data": {
        "company_name": L("株式会社FINORA（仮）", "FINORA Inc. (placeholder)", "FINORA Inc. (provisório)"),
        "representative": L("代表取締役 黒崎 龍一", "Ryuichi Kurozaki, CEO", "Ryuichi Kurozaki, CEO"),
        "established": L("2026年（仮）", "2026 (placeholder)", "2026 (provisório)"),
        "capital": L("1,000万円（仮）", "JPY 10 million (placeholder)", "JPY 10 milhões (provisório)"),
        "address": L("東京都千代田区丸の内1-1-1（仮）", "1-1-1 Marunouchi, Chiyoda-ku, Tokyo (placeholder)", "1-1-1 Marunouchi, Chiyoda-ku, Tóquio (provisório)"),
        "business": L("投資管理・資産コンサルティング向けSaaSの開発・提供", "Development and provision of SaaS for investment management and wealth consulting",
                      "Desenvolvimento e oferta de SaaS para gestão de investimentos e consultoria patrimonial"),
        "employees": L("10名（仮）", "10 (placeholder)", "10 (provisório)"), "phone": L("03-0000-0000（仮）", "+81-3-0000-0000", "+81-3-0000-0000"),
        "email": L("info@finora.co.jp", "info@finora.co.jp", "info@finora.co.jp"),
        "message_title": L("すべての資産に、確かな判断を。", "Sound decisions for every asset.", "Decisões sólidas para cada patrimônio."),
        "message_body": L("FINORAは、資産と負債、キャッシュフローを一つにつなぎ、コンサルタントとお客様がデータに基づいて判断できる環境をつくります。（この文章は仮のものです。管理画面から編集してください）",
                          "FINORA connects assets, liabilities and cash flow in one place so consultants and clients can decide based on data. (Placeholder text — edit it in the admin screen.)",
                          "A FINORA une ativos, passivos e fluxo de caixa em um só lugar para que consultores e clientes decidam com base em dados. (Texto provisório — edite no painel.)"),
        "message_signature": L("代表取締役 黒崎 龍一", "Ryuichi Kurozaki, CEO", "Ryuichi Kurozaki, CEO"),
        "access_note": L("JR東京駅 丸の内北口より徒歩5分（仮）", "5 min walk from JR Tokyo Station, Marunouchi North Exit (placeholder)", "5 min a pé da Estação de Tóquio (provisório)"),
        "map_url": "https://maps.google.com/?q=Tokyo+Station", "message_image": "", "social_x": "", "social_facebook": "", "social_linkedin": "", "social_instagram": "", "social_youtube": "",
    }})
    items = [
        ("service", L("資産の一元管理", "Unified asset management", "Gestão unificada de ativos"), L("株式・債券・不動産・暗号資産まで、すべての資産と負債を一つの画面で管理します。", "Manage stocks, bonds, real estate and crypto together with liabilities on one screen.", "Gerencie ações, títulos, imóveis e cripto junto com passivos em uma única tela."), None, None, 1),
        ("service", L("AIインサイト", "AI insights", "Insights de IA"), L("根拠が見えるAI分析で、リスクと改善提案を分かりやすく示します。", "Explainable AI analysis shows risks and improvement proposals clearly.", "Análises de IA explicáveis mostram riscos e propostas de melhoria."), None, None, 2),
        ("service", L("電子契約・請求", "E-contracts & billing", "Contratos eletrônicos e cobrança"), L("重要事項説明から電子署名、請求・カード決済までをオンラインで完結します。", "From disclosures and e-signatures to invoicing and card payments — all online.", "De divulgações e assinaturas a faturas e pagamentos com cartão — tudo online."), None, None, 3),
        ("news", L("公式サイトを公開しました", "Our official website is live", "Nosso site oficial está no ar"), L("FINORAの公式サイトを公開しました。今後、最新情報をこちらでお知らせします。（仮）", "We launched the FINORA official website. Updates will be posted here. (placeholder)", "Lançamos o site oficial da FINORA. As novidades serão publicadas aqui. (provisório)"), "2026-09-26", "notice", 0),
        ("news", L("FINORA サービス提供開始のお知らせ", "FINORA service launch", "Lançamento do serviço FINORA"), L("投資管理・コンサルティングプラットフォーム「FINORA」の提供を開始しました。（仮）", "We have launched FINORA, an investment management and consulting platform. (placeholder)", "Lançamos a FINORA, plataforma de gestão e consultoria de investimentos. (provisório)"), "2026-09-01", "press", 0),
        ("faq", L("無料で試せますか？", "Can I try it for free?", "Posso testar gratuitamente?"), L("はい。新規登録後、すぐに無料でお試しいただけます。", "Yes. You can start a free trial right after signing up.", "Sim. Você pode começar um teste grátis logo após o cadastro."), None, None, 1),
        ("faq", L("データの安全性は？", "How is my data protected?", "Como meus dados são protegidos?"), L("通信の暗号化、重要項目の暗号化保存、2段階認証、操作ログの記録で保護しています。", "Encrypted transport, encrypted sensitive fields, two-factor authentication and audit logs.", "Transmissão criptografada, campos sensíveis criptografados, autenticação em dois fatores e logs de auditoria."), None, None, 2),
        ("faq", L("どの言語に対応していますか？", "Which languages are supported?", "Quais idiomas são suportados?"), L("日本語・英語・ポルトガル語に対応しています。", "Japanese, English and Portuguese.", "Japonês, inglês e português."), None, None, 3),
        ("history", L("会社設立（仮）", "Company founded (placeholder)", "Fundação da empresa (provisório)"), L("", "", ""), "2026-01", None, 1),
        ("history", L("FINORA 提供開始", "FINORA launched", "Lançamento da FINORA"), L("", "", ""), "2026-09", None, 2),
    ]
    await db.site_items.insert_many([{"id": new_id(), "kind": k, "title": ti, "body": bo, "date": d, "category": c, "image": None, "order": o,
                                      "published": True, "created_at": now_iso(), "updated_at": now_iso()} for k, ti, bo, d, c, o in items])
