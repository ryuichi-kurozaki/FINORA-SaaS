"""v3 migration: SaaS plans/subscriptions, platform admin flag, billing demo data, second tenant for isolation tests."""
from datetime import datetime, timedelta

from core import db, new_id, now_iso
from seed import upsert_user

PLANS = [("FREE", "Free", 0), ("TRIAL", "Trial", 1), ("STANDARD", "Standard", 2), ("PRO", "Pro", 3), ("ENTERPRISE", "Enterprise", 4)]


def d(days):
    return (datetime.now().date() + timedelta(days=days)).isoformat()


async def seed_v3(t, pw):
    tid = t["id"]
    for code, name, order in PLANS:
        await db.plans.update_one({"code": code}, {"$setOnInsert": {"id": new_id(), "code": code, "name": name, "order": order, "active": True,
                                                                   "price_monthly": None, "price_yearly": None, "max_customers": None, "description": ""}}, upsert=True)
    admin = await db.users.find_one({"tenant_id": tid, "role": "admin"})
    await db.users.update_one({"id": admin["id"]}, {"$set": {"platform_admin": True}})
    if not t.get("status"):
        await db.tenants.update_one({"id": tid}, {"$set": {"status": "ACTIVE", "owner_user_id": admin["id"], "billing_profile": {
            "company_name": t.get("name"), "representative": admin.get("name"), "address": "東京都千代田区丸の内1-1-1", "phone": "03-0000-0000",
            "email": admin["email"], "registration_no": "T0000000000000", "bank_info": "FINORA銀行 丸の内支店 普通 1234567 フィノラ(カ", "invoice_note": "お振込手数料はご負担ください。"}}})
    await db.saas_subscriptions.update_one({"tenant_id": tid}, {"$setOnInsert": {"id": new_id(), "plan_code": "PRO", "start_date": d(-400), "renewal_date": d(30),
                                                                                "billing_period": "monthly", "amount": None, "status": "ACTIVE", "payment_status": "paid",
                                                                                "created_at": now_iso()}}, upsert=True)
    if await db.contracts.find_one({"tenant_id": tid}):
        return
    clients = {c["name"]: c for c in await db.clients.find({"tenant_id": tid}).to_list(100)}
    specs = [("佐藤 健一", "資産運用顧問契約", "月額コンサルティング", "MONTHLY", 30000), ("山本 美咲", "法人財務アドバイザリー", "月額法人顧問", "MONTHLY", 50000),
             ("Ana Paula Ferreira", "ポートフォリオ診断", "単発診断", "ONE_TIME", 100000)]
    cons = {}
    for name, cname, svc, ft, fee in specs:
        c = clients.get(name) or next((x for x in clients.values() if name in (x.get("corporate_name") or "") or name in (x.get("name") or "")), None)
        if not c:
            continue
        doc = {"id": new_id(), "tenant_id": tid, "client_id": c["id"], "name": cname, "service_name": svc, "description": svc, "fee_type": ft, "fee": fee,
               "tax_mode": "exclusive", "tax_rate": 10, "start_date": d(-120), "end_date": None, "billing_cycle": ft, "billing_day": 1,
               "payment_terms_days": 30, "auto_renew": "yes", "status": "ACTIVE", "created_at": now_iso(), "updated_at": now_iso(), "created_by": admin["id"]}
        await db.contracts.insert_one(doc)
        cons[name] = doc
    ym = datetime.now().strftime("%Y%m")
    seq = 0

    async def inv(con, issue, due, paid, status):
        nonlocal seq
        seq += 1
        sub = con["fee"]
        tax = round(sub * 0.1)
        doc = {"id": new_id(), "tenant_id": tid, "number": f"INV-{ym}-{seq:04d}", "client_id": con["client_id"], "contract_id": con["id"], "contract_name": con["name"],
               "period": None, "issue_date": issue, "due_date": due, "items": [{"description": con["service_name"], "quantity": 1, "unit_price": sub}],
               "tax_rate": 10, "tax_mode": "exclusive", "subtotal": sub, "tax": tax, "total": sub + tax, "paid": paid, "balance": sub + tax - paid,
               "status": status, "notes": "", "created_by": admin["id"], "created_at": now_iso(), "updated_at": now_iso()}
        await db.invoices.insert_one(doc)
        if paid:
            await db.payments.insert_one({"id": new_id(), "tenant_id": tid, "client_id": con["client_id"], "invoice_id": doc["id"], "invoice_number": doc["number"],
                                          "date": d(-5), "amount": paid, "method": "BANK_TRANSFER", "reference": "", "notes": "", "created_by": admin["id"],
                                          "created_by_name": admin.get("name"), "created_at": now_iso()})
    if "佐藤 健一" in cons:
        await inv(cons["佐藤 健一"], d(-35), d(-5), 33000, "PAID")
        await inv(cons["佐藤 健一"], d(-3), d(27), 0, "ISSUED")
    if "山本 美咲" in cons:
        await inv(cons["山本 美咲"], d(-40), d(-10), 0, "ISSUED")
    if "Ana Paula Ferreira" in cons:
        await inv(cons["Ana Paula Ferreira"], d(-20), d(10), 60000, "PARTIALLY_PAID")
    await db.counters.update_one({"tenant_id": tid, "key": f"invoice-{ym}"}, {"$set": {"seq": seq}}, upsert=True)
    if not await db.tenants.find_one({"slug": "b-consulting"}):
        tb = {"id": new_id(), "slug": "b-consulting", "name": "Bコンサルティング合同会社", "status": "ACTIVE", "created_at": now_iso()}
        await db.tenants.insert_one(tb)
        await upsert_user(tb["id"], "consultantb@finora.co.jp", "鈴木 大輔", "admin", pw)
        ob = await db.users.find_one({"email": "consultantb@finora.co.jp"})
        await db.tenants.update_one({"id": tb["id"]}, {"$set": {"owner_user_id": ob["id"]}})
        cb = {"id": new_id(), "tenant_id": tb["id"], "client_type": "individual", "name": "高橋 誠", "status": "active", "consultant_id": ob["id"],
              "created_at": now_iso(), "updated_at": now_iso()}
        await db.clients.insert_one(cb)
        await upsert_user(tb["id"], "clientb@finora.co.jp", "高橋 誠", "client", pw, cb["id"])
        await db.assets.insert_one({"id": new_id(), "tenant_id": tb["id"], "client_id": cb["id"], "asset_class": "deposit", "name": "普通預金", "currency": "JPY",
                                    "quantity": 1, "acquisition_price": 5000000, "current_price": 5000000, "price_date": d(0), "created_at": now_iso(), "updated_at": now_iso()})
        con = {"id": new_id(), "tenant_id": tb["id"], "client_id": cb["id"], "name": "B社 顧問契約", "service_name": "月額顧問", "fee_type": "MONTHLY", "fee": 20000,
               "tax_mode": "exclusive", "tax_rate": 10, "start_date": d(-60), "status": "ACTIVE", "payment_terms_days": 30, "created_at": now_iso()}
        await db.contracts.insert_one(con)
        await db.invoices.insert_one({"id": new_id(), "tenant_id": tb["id"], "number": f"INV-{ym}-0001", "client_id": cb["id"], "contract_id": con["id"],
                                      "contract_name": con["name"], "issue_date": d(-2), "due_date": d(28), "items": [{"description": "月額顧問", "quantity": 1, "unit_price": 20000}],
                                      "tax_rate": 10, "tax_mode": "exclusive", "subtotal": 20000, "tax": 2000, "total": 22000, "paid": 0, "balance": 22000,
                                      "status": "ISSUED", "notes": "", "created_at": now_iso(), "updated_at": now_iso()})
        await db.saas_subscriptions.insert_one({"id": new_id(), "tenant_id": tb["id"], "plan_code": "STANDARD", "start_date": d(-60), "renewal_date": d(30),
                                                "billing_period": "monthly", "amount": None, "status": "ACTIVE", "payment_status": "paid", "created_at": now_iso()})
