import sys, requests

API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0]
tk = requests.post(f"{API}/api/auth/login", json={"email": "ryuichi.kurozaki@gmail.com", "password": "Finora2026!"}).json()["access_token"]
H = {"Authorization": f"Bearer {tk}"}
rows = requests.get(f"{API}/api/platform/tenants", headers=H).json()
tgt = [r for r in rows if r.get("owner_email") == "consultantb@finora.co.jp"] or rows
r = tgt[0]
print("before:", r["name"], "amount", r["amount"], "fixed", r.get("fixed_fee"))
print("set 77000:", requests.put(f"{API}/api/platform/tenants/{r['id']}", headers=H, json={"fixed_fee": 77000}).json())
row = [x for x in requests.get(f"{API}/api/platform/tenants", headers=H).json() if x["id"] == r["id"]][0]
print("after:", row["amount"], "fixed", row.get("fixed_fee"))
tb = requests.post(f"{API}/api/auth/login", json={"email": "consultantb@finora.co.jp", "password": "Finora2026!"}).json()["access_token"]
sub = requests.get(f"{API}/api/subscription", headers={"Authorization": f"Bearer {tb}"}).json()
print("tenant sees pricing:", sub["pricing"])
nt = requests.get(f"{API}/api/notifications", headers={"Authorization": f"Bearer {tb}"}).json()
print("notif:", [n["kind"] for n in nt["items"][:3]])
print("clear:", requests.put(f"{API}/api/platform/tenants/{r['id']}", headers=H, json={"clear_fixed_fee": True}).json())
row = [x for x in requests.get(f"{API}/api/platform/tenants", headers=H).json() if x["id"] == r["id"]][0]
print("after clear:", row["amount"], "fixed", row.get("fixed_fee"))
log = requests.get(f"{API}/api/platform/email-log?kind=saas_fee", headers=H).json()
print("email log:", [(x["to"], x["subject"], x["status"]) for x in log.get("items", [])][:4])
