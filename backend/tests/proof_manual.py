import requests

API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0]
H = {"Authorization": "Bearer " + requests.post(f"{API}/api/auth/login", json={"email": "ryuichi.kurozaki@gmail.com", "password": "Finora2026!"}).json()["access_token"]}

rows = requests.get(f"{API}/api/econtracts?type=CONSULTING", headers=H).json()
print("statuses:", sorted({r["status"] for r in rows}))
act = [r for r in rows if r["status"] in ("ACTIVE", "ENDED")]
print("certifiable:", len(act))
r = act[0]
print("target:", r["number"], r["status"], r["client_name"])
res = requests.post(f"{API}/api/econtracts/{r['id']}/send-proof", headers=H)
print("send-proof:", res.status_code, res.json())
pre = [x for x in rows if x["status"] in ("DRAFT", "IMPORTANT_INFO_SENT", "CONTRACT_SENT")]
if pre:
    print("pre-active blocked:", requests.post(f"{API}/api/econtracts/{pre[0]['id']}/send-proof", headers=H).status_code)
docs = requests.get(f"{API}/api/documents?client_id={r['client_id']}", headers=H).json()
print("client docs (latest 3):", [(d.get("filename"), d.get("category")) for d in docs[:3]])
log = requests.get(f"{API}/api/mail-log?kind=econtract", headers=H).json()
print("emails:", [(x["to"], x["subject"], x["status"]) for x in log.get("items", [])][:3])
