import base64, random, requests

API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0]
EMAIL = f"autosign{random.randint(1000,9999)}@example.com"
PW = "Finora2026!"

print("signup:", requests.post(f"{API}/api/public/signup", json={
    "name": "自動署名テスト", "company_name": "AutoSign テスト合同会社", "email": EMAIL, "password": PW, "plan_code": "TRIAL"}).json())
tk = requests.post(f"{API}/api/auth/login", json={"email": EMAIL, "password": PW}).json()["access_token"]
H = {"Authorization": f"Bearer {tk}"}

print("client create before contract:", requests.post(f"{API}/api/data/clients", headers=H, json={"name": "テスト顧客", "email": "c@example.com"}).status_code)

ec = requests.get(f"{API}/api/econtracts?type=FINORA_SAAS&mine=true", headers=H).json()
c = ec[0] if isinstance(ec, list) else ec["items"][0]
cid = c["id"]
print("contract:", c["number"], c["status"])
d = requests.get(f"{API}/api/econtracts/{cid}", headers=H).json()
for doc in d.get("documents", d.get("docs", [])) or []:
    print("view:", requests.post(f"{API}/api/econtracts/{cid}/view/{doc['id']}", headers=H).status_code)
print("confirm:", requests.post(f"{API}/api/econtracts/{cid}/confirm", headers=H).json())
d = requests.get(f"{API}/api/econtracts/{cid}", headers=H).json()
for doc in d.get("documents", d.get("docs", [])) or []:
    requests.post(f"{API}/api/econtracts/{cid}/view/{doc['id']}", headers=H)
png = "data:image/png;base64," + base64.b64encode(bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6300010000050001"
                                                                "0d0a2db40000000049454e44ae426082")).decode()
print("sign:", requests.post(f"{API}/api/econtracts/{cid}/sign", headers=H, json={"agree": True, "name": "自動署名テスト", "signature_png": png}).json())
print("me tenant:", requests.get(f"{API}/api/auth/me", headers=H).json().get("tenant"))
r = requests.post(f"{API}/api/data/clients", headers=H, json={"name": "テスト顧客", "email": "c@example.com"})
print("client create after contract:", r.status_code, r.text[:200])
