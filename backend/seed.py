import os
import random
from datetime import datetime, timedelta

from core import db, new_id, now_iso, hash_password, verify_password, encrypt
from analytics import DEFAULT_FX, enrich, summarize, INVEST


def d(days):
    return (datetime.now() + timedelta(days=days)).date().isoformat()


def month_back(n):
    y, m = datetime.now().year, datetime.now().month - n
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


async def upsert_user(tenant_id, email, name, role, password, client_id=None):
    u = await db.users.find_one({"email": email})
    if not u:
        await db.users.insert_one({"id": new_id(), "tenant_id": tenant_id, "email": email, "name": name, "role": role,
                                   "client_id": client_id, "active": True, "lang": "ja",
                                   "password_hash": hash_password(password), "created_at": now_iso()})
    elif not verify_password(password, u["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})
    return await db.users.find_one({"email": email})


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.sessions.create_index("id")
    for c in ("clients", "accounts", "assets", "liabilities", "cashflows", "consulting", "tasks", "documents", "snapshots"):
        await db[c].create_index([("tenant_id", 1), ("client_id", 1)])
        await db[c].create_index("id")
    await db.audit_logs.create_index([("tenant_id", 1), ("at", -1)])
    await db.snapshots.create_index([("tenant_id", 1), ("client_id", 1), ("date", 1)])


CLIENTS = [
    {"client_type": "individual", "name": "佐藤 健一", "email": "k.sato@example.jp", "phone": "090-1234-5678",
     "address": "東京都港区南青山3-1-1", "occupation": "医師（開業医）", "family": "配偶者、子2名", "related_corps": "医療法人 佐藤会",
     "annual_income": 28000000, "income": 19600000, "investment_experience": "10年以上", "investment_purpose": "老後資金・資産承継",
     "risk_tolerance": "moderate", "status": "active", "notes": "米国株比率の上昇と住宅ローン金利を注視", "_c": "consultant"},
    {"client_type": "corporate", "name": "山本 美咲", "corporate_name": "株式会社ノヴァテック", "email": "cfo@novatech.example.jp",
     "phone": "03-5555-0101", "address": "東京都渋谷区道玄坂2-10-7", "business": "SaaS開発・ITコンサルティング",
     "annual_income": 384000000, "income": 52000000, "investment_experience": "5年", "investment_purpose": "余剰資金運用・M&A準備",
     "risk_tolerance": "moderate", "status": "active", "notes": "本社ビル借入の借換検討中", "_c": "consultant"},
    {"client_type": "individual", "name": "Ana Paula Ferreira", "email": "ana.ferreira@example.com", "phone": "080-9876-5432",
     "address": "東京都目黒区中目黒1-2-3", "occupation": "起業家（貿易業）", "family": "Single", "annual_income": 13200000,
     "income": 9800000, "investment_experience": "7 anos", "investment_purpose": "Crescimento patrimonial / retorno ao Brasil",
     "risk_tolerance": "aggressive", "status": "active", "notes": "BRL建て資産の為替リスク", "_c": "consultant"},
    {"client_type": "corporate", "name": "鈴木 大輔", "corporate_name": "株式会社サクラ不動産", "email": "info@sakura-re.example.jp",
     "phone": "06-6666-0202", "address": "大阪府大阪市北区梅田1-1-1", "business": "不動産賃貸・管理", "annual_income": 78000000,
     "income": 9000000, "investment_experience": "15年", "investment_purpose": "賃貸収益の安定化", "risk_tolerance": "",
     "status": "prospect", "notes": "借入比率が高い", "_c": "admin"},
]

# (client_idx, account_idx or None, class, name, ticker, owner, country, sector, currency, acq_date, acq_price, qty, cur_price, div, interest)
ASSETS = [
    (0, 0, "deposit", "普通預金", "", "individual", "JP", "", "JPY", "2015-04-01", 1, 18000000, 1, 0, 1800),
    (0, 1, "jp_stock", "トヨタ自動車", "7203", "individual", "JP", "automotive", "JPY", "2019-06-10", 1850, 3000, 2900, 225000, 0),
    (0, 2, "foreign_stock", "Apple Inc.", "AAPL", "individual", "US", "technology", "USD", "2020-03-20", 120, 400, 210, 400, 0),
    (0, 2, "foreign_stock", "NVIDIA", "NVDA", "individual", "US", "technology", "USD", "2022-10-14", 45, 300, 135, 12, 0),
    (0, 2, "etf", "Vanguard S&P 500 ETF", "VOO", "individual", "US", "diversified", "USD", "2021-01-15", 380, 150, 560, 1020, 0),
    (0, 1, "fund", "eMAXIS Slim 全世界株式", "", "individual", "GLOBAL", "diversified", "JPY", "2020-01-06", 1, 6000000, 1.4, 0, 0),
    (0, 2, "bond", "US Treasury 2034", "UST", "individual", "US", "government", "USD", "2024-05-01", 50000, 1, 48500, 0, 2100),
    (0, 3, "crypto", "Bitcoin", "BTC", "individual", "GLOBAL", "digital_asset", "JPY", "2021-05-20", 5500000, 0.8, 15200000, 0, 0),
    (0, None, "real_estate", "港区南青山マンション", "", "individual", "JP", "real_estate", "JPY", "2016-04-01", 85000000, 1, 98000000, 0, 0),
    (0, None, "insurance", "終身保険（解約返戻金）", "", "individual", "JP", "", "JPY", "2012-08-01", 5000000, 1, 6500000, 0, 0),
    (0, 1, "gold", "純金積立", "", "individual", "GLOBAL", "commodity", "JPY", "2019-02-01", 8500, 1000, 14800, 0, 0),
    (0, 1, "pension", "iDeCo", "", "individual", "JP", "", "JPY", "2017-01-01", 3000000, 1, 4200000, 0, 0),
    (1, 4, "deposit", "当座・普通預金", "", "corporate", "JP", "", "JPY", "2018-04-01", 1, 120000000, 1, 0, 12000),
    (1, 5, "jp_stock", "ソニーグループ", "6758", "corporate", "JP", "technology", "JPY", "2021-09-01", 2400, 10000, 3300, 200000, 0),
    (1, 6, "foreign_stock", "Microsoft", "MSFT", "corporate", "US", "technology", "USD", "2022-02-10", 280, 500, 430, 1500, 0),
    (1, 6, "deposit", "USD Deposit", "", "corporate", "US", "", "USD", "2023-01-01", 1, 200000, 1, 0, 6000),
    (1, 5, "bond", "日本国債 10年", "JGB", "corporate", "JP", "government", "JPY", "2024-03-01", 1, 30000000, 0.98, 0, 270000),
    (1, None, "unlisted", "AIスタートアップ出資", "", "corporate", "JP", "technology", "JPY", "2022-07-01", 20000000, 1, 35000000, 0, 0),
    (1, None, "real_estate", "本社ビル（渋谷）", "", "corporate", "JP", "real_estate", "JPY", "2019-11-01", 180000000, 1, 210000000, 0, 0),
    (2, 7, "deposit", "Conta corrente Itaú", "", "individual", "BR", "", "BRL", "2020-01-01", 1, 350000, 1, 0, 0),
    (2, 7, "bond", "Tesouro IPCA+ 2035", "", "individual", "BR", "government", "BRL", "2023-02-01", 400000, 1, 452000, 0, 45000),
    (2, 8, "etf", "TOPIX連動型ETF", "1306", "individual", "JP", "diversified", "JPY", "2022-04-01", 2000, 2000, 2800, 90000, 0),
    (2, 8, "foreign_stock", "Petrobras ADR", "PBR", "individual", "BR", "energy", "USD", "2023-06-01", 12, 2000, 14.5, 3600, 0),
    (2, None, "crypto", "Ethereum", "ETH", "individual", "GLOBAL", "digital_asset", "JPY", "2022-08-01", 300000, 10, 520000, 0, 0),
    (2, None, "cash", "現金", "", "individual", "JP", "", "JPY", "2024-01-01", 1, 3000000, 1, 0, 0),
    (3, 9, "deposit", "普通預金", "", "corporate", "JP", "", "JPY", "2010-01-01", 1, 25000000, 1, 0, 2500),
    (3, None, "real_estate", "梅田レジデンス", "", "corporate", "JP", "real_estate", "JPY", "2014-05-01", 220000000, 1, 236000000, 0, 0),
    (3, None, "real_estate", "難波オフィスビル", "", "corporate", "JP", "real_estate", "JPY", "2017-09-01", 160000000, 1, 168000000, 0, 0),
    (3, None, "real_estate", "京都町家ホテル", "", "corporate", "JP", "real_estate", "JPY", "2020-03-01", 70000000, 1, 76000000, 0, 0),
]
ACCOUNTS = [
    (0, "三菱UFJ銀行", "bank", "domestic", "individual", "JPY"), (0, "SBI証券", "securities", "domestic", "individual", "JPY"),
    (0, "Interactive Brokers", "securities", "overseas", "individual", "USD"), (0, "bitFlyer", "crypto_exchange", "domestic", "individual", "JPY"),
    (1, "みずほ銀行", "bank", "domestic", "corporate", "JPY"), (1, "野村證券", "securities", "domestic", "corporate", "JPY"),
    (1, "HSBC Hong Kong", "bank", "overseas", "corporate", "USD"), (2, "Itaú Unibanco", "bank", "overseas", "individual", "BRL"),
    (2, "楽天証券", "securities", "domestic", "individual", "JPY"), (3, "りそな銀行", "bank", "domestic", "corporate", "JPY"),
]
LIABS = [
    (0, "mortgage", "三井住友銀行", "individual", 70000000, 48000000, 0.6, "variable", 210000, "2016-04-01", 420, "2051-03-31", "港区南青山マンション"),
    (0, "auto_loan", "トヨタファイナンス", "individual", 3000000, 1200000, 2.5, "fixed", 55000, "2023-01-01", 60, d(300), ""),
    (1, "business_loan", "日本政策金融公庫", "corporate", 100000000, 72000000, 1.2, "fixed", 1400000, "2021-04-01", 84, "2028-03-31", ""),
    (1, "real_estate_loan", "みずほ銀行", "corporate", 150000000, 110000000, 0.9, "variable", 600000, "2019-11-01", 300, "2044-10-31", "本社ビル（渋谷）"),
    (2, "card_loan", "楽天カード", "individual", 800000, 800000, 15.0, "fixed", 50000, "2025-01-01", 24, d(200), ""),
    (3, "real_estate_loan", "りそな銀行", "corporate", 420000000, 380000000, 1.5, "variable", 3200000, "2014-05-01", 360, "2044-04-30", "梅田レジデンス・難波オフィスビル"),
]
CFS = [
    (0, "income", "salary", "給与（手取）", 1650000), (0, "income", "dividend", "配当", 45000), (0, "expense", "living", "生活費", 520000),
    (0, "expense", "tax", "税金", 260000), (0, "expense", "social_insurance", "社会保険", 120000), (0, "expense", "insurance", "保険料", 60000),
    (0, "expense", "loan_repayment", "ローン返済", 265000), (0, "expense", "investment", "積立投資", 300000), (0, "expense", "other", "その他", 80000),
    (1, "income", "business_income", "売上", 32000000), (1, "income", "interest", "受取利息", 22500), (1, "expense", "business_expense", "事業経費・人件費", 24000000),
    (1, "expense", "tax", "法人税等", 2500000), (1, "expense", "loan_repayment", "借入返済", 2000000), (1, "expense", "investment", "余剰資金運用", 1500000),
    (1, "expense", "insurance", "法人保険", 300000), (2, "income", "business_income", "事業収入", 1100000), (2, "expense", "living", "生活費", 450000),
    (2, "expense", "tax", "税金", 150000), (2, "expense", "social_insurance", "社会保険", 80000), (2, "expense", "loan_repayment", "カードローン返済", 50000),
    (2, "expense", "investment", "投資", 150000), (2, "expense", "other", "その他", 100000), (3, "income", "real_estate_income", "賃料収入", 6500000),
    (3, "expense", "business_expense", "管理費・修繕", 2000000), (3, "expense", "loan_repayment", "借入返済", 3200000), (3, "expense", "tax", "税金", 800000),
]
CONSULT = [
    (0, "hearing", -420, "初回ヒアリング", "老後資金と子の教育資金、医療法人の事業承継について意向確認。", "", "done"),
    (0, "purpose", -410, "投資目的の整理", "65歳時点で純資産5億円、年間配当収入600万円を目標。", "", "done"),
    (0, "issue", -120, "課題抽出", "米国テック株への集中、変動金利住宅ローンの金利上昇リスク。", "", "done"),
    (0, "proposal", -95, "改善提案", "米国株の一部を全世界株式・債券へリバランス。住宅ローン固定化の試算を提示。", "", "done"),
    (0, "meeting", -90, "定例面談（Q1）", "リバランス方針に合意。固定金利の見積取得を依頼。", "", "done"),
    (0, "meeting", -30, "定例面談（Q2）", "固定金利見積を確認。NVIDIAの一部利確を検討。", "住宅ローン借換の比較資料を送付", "open"),
    (1, "analysis", -200, "現状分析", "余剰資金1.2億円が預金に滞留。国債・社債ラダーを提案。", "", "done"),
    (1, "meeting", -60, "CFO面談", "本社ビル借入の借換と余剰資金運用方針を協議。", "借換シミュレーションを提示", "open"),
    (2, "meeting", -45, "Reunião de revisão", "Discussão sobre risco cambial BRL/JPY e quitação do empréstimo no cartão.", "Enviar plano de quitação", "open"),
]
TASKS = [
    (0, "meeting", "佐藤様 定例面談（Q3）", 5, "open", "high"), (0, "document_deadline", "佐藤様 確定申告書の提出", -2, "open", "high"),
    (0, "dividend", "トヨタ自動車 配当入金予定", 20, "open", "low"), (0, "insurance_renewal", "終身保険 更新確認", 40, "open", "medium"),
    (1, "loan_renewal", "ノヴァテック 借入更新協議", 10, "open", "high"), (3, "next_contact", "サクラ不動産 次回連絡", 1, "open", "medium"),
    (None, "internal", "月次ポートフォリオレビュー", 3, "open", "medium"), (2, "next_contact", "Ana様 返済計画送付", -1, "done", "medium"),
]


async def seed_demo(tenant_id, consultant_id, admin_id):
    rnd = random.Random(42)
    cids, acct_ids = [], []
    for c in CLIENTS:
        c = dict(c)
        owner = consultant_id if c.pop("_c") == "consultant" else admin_id
        doc = {"id": new_id(), "tenant_id": tenant_id, **c, "consultant_id": owner, "created_at": now_iso(), "updated_at": now_iso()}
        for k in ("phone", "address", "family", "notes"):
            doc[k] = encrypt(doc.get(k))
        await db.clients.insert_one(doc)
        cids.append(doc["id"])
    for ci, inst, typ, reg, own, cur in ACCOUNTS:
        aid = new_id()
        await db.accounts.insert_one({"id": aid, "tenant_id": tenant_id, "client_id": cids[ci], "institution": inst, "account_type": typ,
                                      "region": reg, "owner_type": own, "currency": cur, "account_number": encrypt(f"{rnd.randint(1000000, 9999999)}"),
                                      "created_at": now_iso(), "updated_at": now_iso()})
        acct_ids.append(aid)
    for ci, ai, cls, name, tk, own, ctry, sec, cur, ad, ap, q, cp, div, intr in ASSETS:
        await db.assets.insert_one({"id": new_id(), "tenant_id": tenant_id, "client_id": cids[ci], "account_id": acct_ids[ai] if ai is not None else None,
                                    "asset_class": cls, "name": name, "ticker": tk, "owner_type": own, "country": ctry, "sector": sec,
                                    "currency": cur, "acquired_date": ad, "acquisition_price": float(ap), "quantity": float(q),
                                    "current_price": float(cp), "realized_pl": 0.0, "dividend_annual": float(div), "interest_annual": float(intr),
                                    "created_at": now_iso(), "updated_at": now_iso()})
    for ci, typ, inst, own, orig, bal, rate, rt, mp, sd, term, md, col in LIABS:
        await db.liabilities.insert_one({"id": new_id(), "tenant_id": tenant_id, "client_id": cids[ci], "liability_type": typ, "institution": inst,
                                         "owner_type": own, "original_amount": float(orig), "balance": float(bal), "interest_rate": rate,
                                         "rate_type": rt, "monthly_payment": float(mp), "start_date": sd, "term_months": float(term),
                                         "maturity_date": md, "collateral": col, "created_at": now_iso(), "updated_at": now_iso()})
    for ci, dr, cat, name, amt in CFS:
        await db.cashflows.insert_one({"id": new_id(), "tenant_id": tenant_id, "client_id": cids[ci], "direction": dr, "category": cat,
                                       "name": name, "amount": float(amt), "frequency": "monthly", "created_at": now_iso(), "updated_at": now_iso()})
    for ci, kind, days, title, content, na, st in CONSULT:
        await db.consulting.insert_one({"id": new_id(), "tenant_id": tenant_id, "client_id": cids[ci], "kind": kind, "date": d(days), "title": title,
                                        "content": encrypt(content), "next_action": na, "status": st, "created_at": now_iso(), "updated_at": now_iso()})
    for ci, kind, title, days, st, pr in TASKS:
        await db.tasks.insert_one({"id": new_id(), "tenant_id": tenant_id, "client_id": cids[ci] if ci is not None else None, "kind": kind,
                                   "title": title, "due_date": d(days), "status": st, "priority": pr,
                                   "assignee_id": admin_id if ci == 3 else consultant_id, "created_at": now_iso(), "updated_at": now_iso()})
    fx = DEFAULT_FX
    bm = 100.0
    for i in range(24, -1, -1):
        bm *= 1 + 0.006 + rnd.uniform(-0.025, 0.025) - (0.03 if 14 <= i <= 16 else 0)
        await db.benchmarks.insert_one({"id": new_id(), "tenant_id": tenant_id, "date": month_back(i), "value": round(bm, 2)})
    for ci, cid in enumerate(cids):
        assets = [enrich({"asset_class": a[2], "currency": a[8], "acquisition_price": a[10], "quantity": a[11], "current_price": a[12]}, fx)
                  for a in ASSETS if a[0] == ci]
        s = summarize(assets, [{"balance": l[5]} for l in LIABS if l[0] == ci])
        other = s["total_assets"] - s["invested_value"]
        for i in range(24, 0, -1):
            f = 0.80 + 0.20 * (24 - i) / 24 + rnd.uniform(-0.02, 0.02) - (0.06 if 14 <= i <= 16 else 0)
            inv = s["invested_value"] * f
            tl = s["total_liabilities"] * (1 + 0.08 * i / 24)
            ta = other * (0.9 + 0.1 * (24 - i) / 24) + inv
            await db.snapshots.insert_one({"id": new_id(), "tenant_id": tenant_id, "client_id": cid, "date": month_back(i),
                                           "total_assets": ta, "total_liabilities": tl, "net_worth": ta - tl,
                                           "invested_value": inv, "principal": s["principal"]})
    return cids


async def seed():
    await ensure_indexes()
    t = await db.tenants.find_one({"slug": "finora-demo"})
    if not t:
        t = {"id": new_id(), "slug": "finora-demo", "name": "FINORA Wealth Partners", "plan": "premium", "created_at": now_iso()}
        await db.tenants.insert_one(t)
    pw = os.environ["DEMO_PASSWORD"]
    admin = await upsert_user(t["id"], os.environ["ADMIN_EMAIL"].lower(), "Ryuichi Kurozaki", "admin", os.environ["ADMIN_PASSWORD"])
    cons = await upsert_user(t["id"], "consultant@finora.co.jp", "田中 翔", "consultant", pw)
    if not await db.clients.find_one({"tenant_id": t["id"]}):
        cids = await seed_demo(t["id"], cons["id"], admin["id"])
        await upsert_user(t["id"], "client@finora.co.jp", "佐藤 健一", "client", pw, cids[0])
    else:
        await upsert_user(t["id"], "client@finora.co.jp", "佐藤 健一", "client", pw)
