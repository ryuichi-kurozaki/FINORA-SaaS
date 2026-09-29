import base64, hashlib, hmac, json, os, random, sys, requests

API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0]
SECRET = "previewtestsecret"
email = sys.argv[1] if len(sys.argv) > 1 else "client@finora.co.jp"
uid = sys.argv[2] if len(sys.argv) > 2 else "Utestuser001"

tk = requests.post(f"{API}/api/auth/login", json={"email": email, "password": "Finora2026!"}).json()["access_token"]
H = {"Authorization": f"Bearer {tk}"}
print("status:", requests.get(f"{API}/api/line/status", headers=H).json())
code = requests.post(f"{API}/api/line/link-code", headers=H).json()["code"]
print("code:", code)


def send(text):
    body = json.dumps({"destination": "x", "events": [{"type": "message", "webhookEventId": f"ev{random.randint(1, 10**12)}",
                                                       "replyToken": "tok", "source": {"type": "user", "userId": uid},
                                                       "message": {"type": "text", "text": text}}]}, ensure_ascii=False).encode()
    sig = base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()
    r = requests.post(f"{API}/api/line/webhook", data=body, headers={"Content-Type": "application/json", "X-Line-Signature": sig})
    print(f"{text!r} -> {r.status_code} {r.text[:80]}")


for m in ["こんにちは", code, "ヘルプ", "通知", "請求", "契約", "面談", "資産", "xyz"]:
    send(m)
print("bad sig ->", requests.post(f"{API}/api/line/webhook", data=b'{"events":[]}', headers={"X-Line-Signature": "bad", "Content-Type": "application/json"}).status_code)
print("linked:", requests.get(f"{API}/api/line/status", headers=H).json())
print("unlink:", requests.delete(f"{API}/api/line/link", headers=H).json())
