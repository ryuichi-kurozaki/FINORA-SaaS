import requests

API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0]


def tok(email, pw="Finora2026!"):
    return {"Authorization": "Bearer " + requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw}).json()["access_token"]}


CH = tok("client@finora.co.jp")
SH = tok("ryuichi.kurozaki@gmail.com")

r = requests.post(f"{API}/api/contract-requests", headers=CH, json={"service_name": "資産運用アドバイザリー（月次）", "note": "月10万円程度で相談したい", "start_date": "2026-07-01", "fee_type": "MONTHLY", "lang": "ja"})
print("create:", r.status_code, r.json())
rid = r.json()["id"]
print("duplicate blocked:", requests.post(f"{API}/api/contract-requests", headers=CH, json={"service_name": "二重申込"}).status_code)
print("client list:", [(x["service_name"], x["status"]) for x in requests.get(f"{API}/api/contract-requests", headers=CH).json()])
staff = requests.get(f"{API}/api/contract-requests?status=PENDING", headers=SH).json()
print("staff pending:", [(x["client_name"], x["service_name"]) for x in staff])
print("staff cannot request:", requests.post(f"{API}/api/contract-requests", headers=SH, json={"service_name": "x"}).status_code)

cl = requests.get(f"{API}/api/data/clients", headers=SH).json()
client_id = [x for x in staff if x["id"] == rid][0]["client_id"]
terms = {"service_name": "資産運用アドバイザリー（月次）", "description": "申込より作成", "fee_type": "MONTHLY", "fee": 100000, "tax_mode": "exclusive",
         "tax_rate": 10, "start_date": "2026-07-01", "end_date": None, "billing_day": 1, "payment_terms_days": 30, "auto_renew": True}
ec = requests.post(f"{API}/api/econtracts", headers=SH, json={"contract_type": "CONSULTING", "client_id": client_id, "lang": "ja", "terms": terms, "request_id": rid})
print("approve->contract:", ec.status_code, ec.json().get("number"))
print("after approve:", [(x["status"], x.get("econtract_number")) for x in requests.get(f"{API}/api/contract-requests", headers=CH).json() if x["id"] == rid])
print("re-approve blocked:", requests.post(f"{API}/api/contract-requests/{rid}/reject", headers=SH, json={"reason": "x"}).status_code)

r2 = requests.post(f"{API}/api/contract-requests", headers=CH, json={"service_name": "却下テスト", "note": "テスト"}).json()
print("reject:", requests.post(f"{API}/api/contract-requests/{r2['id']}/reject", headers=SH, json={"reason": "予算が合いません"}).json()["status"])
r3 = requests.post(f"{API}/api/contract-requests", headers=CH, json={"service_name": "取り下げテスト"}).json()
print("withdraw:", requests.post(f"{API}/api/contract-requests/{r3['id']}/withdraw", headers=CH).json()["status"])
nt = requests.get(f"{API}/api/notifications", headers=CH).json()
print("client notifications:", [n["kind"] for n in (nt if isinstance(nt, list) else nt.get("items", []))][:5])
