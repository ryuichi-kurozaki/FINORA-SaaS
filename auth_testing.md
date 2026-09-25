# Auth Testing Playbook (FINORA)

1. MongoDB: `db.users.find({role:"admin"})` — bcrypt hash starts with `$2b$`; unique index on users.email.
2. API:
```
curl -c cookies.txt -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"ryuichi.kurozaki@gmail.com","password":"Finora2026!"}'
curl -b cookies.txt $API/api/auth/me
```
Login returns {user, access_token} and sets access_token + refresh_token cookies. Bearer header also accepted.
