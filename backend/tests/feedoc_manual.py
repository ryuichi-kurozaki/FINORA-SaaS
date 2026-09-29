import random, requests

API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0]
EMAIL = f"feedoc{random.randint(1000,9999)}@example.com"
PW = "Finora2026!"
print("signup:", requests.post(f"{API}/api/public/signup", json={"name": "料金表示テスト", "company_name": "FeeDoc テスト株式会社", "email": EMAIL, "password": PW, "plan_code": "TRIAL"}).json())
ctk = requests.post(f"{API}/api/auth/login", json={"email": EMAIL, "password": PW}).json()["access_token"]
CH = {"Authorization": f"Bearer {ctk}"}
c = requests.get(f"{API}/api/econtracts?type=FINORA_SAAS&mine=true", headers=CH).json()[0]
print("contract:", c["number"], c["status"], "fee_amount:", c["fee_amount"])


def fee_section(cid, h):
    d = requests.get(f"{API}/api/econtracts/{cid}", headers=h).json()
    doc = [x for x in d["documents"] if not x.get("superseded_by")][0]
    return doc["number"], [s for s in doc["sections"] if "料金" in s.get("heading", "")]


print("doc fee BEFORE:", fee_section(c["id"], CH))

atk = requests.post(f"{API}/api/auth/login", json={"email": "ryuichi.kurozaki@gmail.com", "password": "Finora2026!"}).json()["access_token"]
AH = {"Authorization": f"Bearer {atk}"}
tid = [x for x in requests.get(f"{API}/api/platform/tenants", headers=AH).json() if x["name"].startswith("FeeDoc")][0]["id"]
print("set fixed fee:", requests.put(f"{API}/api/platform/tenants/{tid}", headers=AH, json={"fixed_fee": 77000}).json())
print("doc fee AFTER:", fee_section(c["id"], CH))
row = requests.get(f"{API}/api/econtracts?type=FINORA_SAAS&mine=true", headers=CH).json()[0]
print("list fee_amount:", row["fee_amount"], "status:", row["status"])
print("clear:", requests.put(f"{API}/api/platform/tenants/{tid}", headers=AH, json={"clear_fixed_fee": True}).json())
print("doc fee CLEARED:", fee_section(c["id"], CH))
