# FINORA production deploy (own VPS) — DO NOT touch other sites/services on this server
- SSH: ssh -p 10022 -i /root/.ssh/finora_vps.pem root@160.251.120.127 (Ubuntu 20.04, 11 other nginx sites, pm2 + systemd apps)
- Everything lives in /data/finora-saas (big disk /dev/vdb): backend/ (venv py3.11 via uv), frontend/build, mongo-data, logs, bin/mongodb 7.0.14, acme, swapfile(2G, in fstab; fstab.bak kept)
- systemd (new only): finora-saas-mongo (127.0.0.1:27217, cache 0.25GB), finora-saas-backend (uvicorn 127.0.0.1:8110)
- nginx: /etc/nginx/sites-available/finora-saas (symlinked). Always `nginx -t` then `systemctl reload nginx` (never restart)
- SSL: certbot --cert-name finora-saas (webroot /data/finora-saas/acme), covers finora.co.jp + www.finora.co.jp, renew_hook reloads nginx, dry-run OK. finora.co.jp 301 -> https://www.finora.co.jp
- Prod .env: /data/finora-saas/backend/.env (local copy /root/finora-deploy/backend.env). SEED_DEMO=false, DB finora_saas, Stripe LIVE key, webhook we_1UJZGnFtJwbFJjRZf5o0IHuk -> https://www.finora.co.jp/api/stripe/webhook
- Redeploy backend: rsync -az --delete --exclude tests --exclude __pycache__ --exclude .env --exclude pytest.ini -e "ssh -p 10022 -i /root/.ssh/finora_vps.pem" /app/backend/ root@160.251.120.127:/data/finora-saas/backend/ ; then systemctl restart finora-saas-backend (only this unit)
- Redeploy frontend: cd /app/frontend && REACT_APP_BACKEND_URL= REACT_APP_DEMO_PASSWORD= REACT_APP_DEMO_ADMIN_EMAIL= REACT_APP_DEMO_CONSULTANT_EMAIL= REACT_APP_DEMO_CLIENT_EMAIL= BUILD_PATH=/root/finora-build GENERATE_SOURCEMAP=false yarn build ; rsync -az --delete /root/finora-build/ root@...:/data/finora-saas/frontend/build/
- Server RAM is tight (3.8GB, ~530MB free). FINORA uses ~270MB (mongo ~120MB + api ~150MB)
