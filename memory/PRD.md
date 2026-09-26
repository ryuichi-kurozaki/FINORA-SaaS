# FINORA — PRD

## Original Problem Statement
FINORA 投資管理コンサルティングSaaS（www.finora.co.jp）。個人・法人の資産／投資／負債／キャッシュフロー／金融口座を一元管理し、AI分析・リスク管理・将来シミュレーション・コンサルティング支援を行う。デザイン「Premium FinTech × Near Future」、ブランドカラー Midnight Navy #071A2B / Emerald #00A878 / Gold #C9A227。ロール：管理者・コンサルタント・顧客。Phase 1〜8 の順で開発。

## User Choices
- 【重要】ユーザーとのやり取りは必ず日本語で行うこと（ユーザー指定・全エージェント共通）
- 全Phaseを最後まで実装
- AIは課金なし → 決定論的ルールエンジン（finora-rule-engine-v1、将来LLMに差し替え可能）
- JWT（メール＋パスワード）、2FAは後のPhase
- 多言語：日本語／English／Português
- デモデータ投入

## Architecture
- Backend (FastAPI, modular): core.py (DB/JWT/RBAC/tenant scope/Fernet field encryption/audit), auth_routes.py, crud.py (generic /api/data/{entity}), analytics.py, ai_engine.py, routes_analytics.py, io_routes.py (CSV/Excel, GridFS documents), seed.py
- Frontend (React + shadcn + recharts): AppContext (auth/lang/client scope), config-driven EntityManager, 16 nav pages, html2pdf report export
- Data flow: clients → accounts → assets/liabilities → cashflow → portfolio → analytics → risk → simulation → AI → consulting → reports → monitoring (monthly snapshots auto-recorded)

## Implemented (2026-06)
- Phase1: JWT auth, sessions, brute-force lock, login history + anomaly (new IP), users mgmt, CRM (individual/corporate)
- Phase2: assets (16 classes, multi-currency, FX table), accounts, liabilities
- Phase3: portfolio auto-calc (9 totals + 6 breakdowns), cash flow (monthly/annual/free/investable)
- Phase4: dashboard (7 KPIs, 8 charts, FINORA AI INSIGHT), analytics (annualized return, volatility, MDD, benchmark, Sharpe)
- Phase5: simulation (bull/base/bear, 5/10/20y, contribution, reinvest, 6 stress params), risk (8 indicators, score, alerts)
- Phase6: AI insights + assistant (fact/calc/estimate/ai labels, 6 intents, JA/EN/PT)
- Phase7: consulting records, 11 report types with PDF, documents (upload/download/delete)
- Phase8: tasks + deadline alerts bell, CSV/Excel import/export, audit logs (who/when/what/before/after)
- Testing: iteration_1 — backend 25/25, frontend all flows pass
- Brand logos (4 variants) applied: sidebar, login, favicon, reports
- Public landing page at / (logged-out): hero, brand, data flow, features, AI showcase, target users, security, pricing (contact-based), contact form → /api/public/inquiries (honeypot + 5/h rate limit), admin Inquiries tab, /legal (terms & privacy), JA/EN/PT — iteration_2 all pass
- Demo login one-click autofill (frontend .env REACT_APP_DEMO_*; remove before public launch)
- v2 spec (追加機能・不足機能): client-owned financial data (client CRUD, staff read-only enforced in API), correction requests (consultant→client→resolved), Transactions + positions (avg cost, realized/unrealized, dividends/interest cum.), saved snapshots, daily net-worth history (1M–ALL), price_date/balance_date/source/updated_by_role provenance, FX date & base currency setting, Data Health (13 checks, ok/review/attention, never auto-fix), Goals + goal simulation, Timeline (derived from audit log), Notification Center, consulting requests workflow, record-linked comments, document metadata (client-only upload/delete), task ownership/visibility, AI labels FACT/CALCULATION/SIMULATION/AI INSIGHT/DATA WARNING + health/goals intents, dashboard redesign + client Action Center, audit logs with user_role/client_id/uppercase actions, versioned consents gate, client self-export, optional TOTP 2FA, admin JSON backup, reports: goals/data health/transactions — iteration_3: backend 30/32 (1 legacy-audit fixed, 1 skipped), frontend 100%
- New modules: backend calc.py, features.py, seed_v2.py; frontend pages Transactions, GoalsHealth, ConsultingHub, Timeline, Notifications; components RecordDrawer, CorrectionDialog, CommentThread, HealthPanel, GoalsPanel, NetWorthHistory, SnapshotsPanel, ActionCenter, ConsentGate, SecurityExtras

## Backlog
- P1: market price / FX API providers (source=API), email notifications for deadlines, Data Health warning notifications to consultants, request attachments UI
- P1: admin-owned demo client to exercise consultant isolation in tests; base-currency switch UI
- P2: accounting/bank API integration, scheduled backups, LLM-backed AI (optional, paid)

## Backlog
- P0: 2FA (TOTP)
- P1: LLM plug-in for AI engine (optional, paid), market price / FX API sync, email deadline notifications (cron)
- P1: meeting-minutes AI summarization, per-tenant risk threshold settings
- P2: accounting system / bank API integration, backup UI, multi-tenant signup

## v3 — Consultant membership / contracts / billing (2026-06)
- Consultant signup → own tenant (TRIAL/ACTIVE/SUSPENDED/CANCELLED) + saas_subscription; plans FREE/TRIAL/STANDARD/PRO/ENTERPRISE (prices not hardcoded)
- Roles: FINORA_ADMIN (platform_admin flag) / TENANT_OWNER (admin) / CONSULTANT / CUSTOMER; secondary_consultant_ids
- Customer invitations (PENDING/ACCEPTED/EXPIRED/CANCELLED) — email delivery MOCKED (copy link)
- Consulting contracts (per-customer fees), invoices (embedded items, numbering, tax modes, auto OVERDUE), partial payments, recurring draft generation, billing profile, invoice PDF
- Revenue summary, consultant business overview, clients overview table, customer billing view
- Platform admin (tenants/plans/audit, counts only; suspend blocks login); SaaS ledger separate from customer invoices
- iteration_4: backend 31/31, frontend 100% (ClientDetail hook-order fix applied)
- 2nd demo tenant: consultantb@finora.co.jp / clientb@finora.co.jp
- Backlog: real email (Resend) for invites/invoices, online card payment (Stripe), scheduled monthly invoice job, staff permission UI

## Stripe card payments (2026-06)
- Stripe claimable sandbox (test mode, JP). backend/stripe_payments.py: POST /api/stripe/checkout/invoice (customer pays own invoice balance), POST /api/stripe/checkout/subscription (tenant owner pays FINORA fee = saas_subscriptions.amount set by platform admin), GET /api/payments/status/{session_id}, POST /api/stripe/webhook; payment_transactions collection; idempotent fulfillment → payments(method CREDIT_CARD) + invoice recompute / subscription paid+ACTIVE+renewal extended
- Tax: SaaS fee → Stripe-managed tax (fallback to calc / none); invoices → no Stripe tax (FINORA invoice already includes consumption tax)
- Frontend: invoice-card-pay button (customer), saas-card-pay-btn (Settings), /payment/success & /payment/cancel
- iteration_5: backend 9/9; checkout redirects verified; fulfillment verified via direct call (hosted Stripe page not automated)
- Note: invoice card payments settle to the FINORA platform Stripe account; per-consultant payouts need Stripe Connect (backlog)


## 2026-06 Stripe live key switch
- Preview backend/.env: STRIPE_SECRET_KEY = user's own LIVE key (acct_1TBE8tFtJwbFJjRZ, JP, JPY), STRIPE_MODE=live
- Stripe account NOT yet activated (charges_enabled=false): checkout returns 400 "Your account cannot currently make live charges."
- Stripe errors now return 400 with message (Cloudflare replaces 502 with its own page)
- STRIPE_WEBHOOK_SECRET / STRIPE_PUBLISHABLE_KEY / STRIPE_ACCOUNT_ID still old test values (publishable/account unused in code). Need a live webhook endpoint -> /api/stripe/webhook and its whsec after deploy. Success page polling (/api/payments/status) still marks payments as paid without the webhook.
- App not deployed yet: production secrets must be set via Deployment UI (Secrets)

## 2026-06 Production deploy to own VPS (ConoHa 160.251.120.127)
- Live at https://www.finora.co.jp (apex redirects to www). See /app/memory/DEPLOY_VPS.md
- New SEED_DEMO env flag: false in prod -> only admin tenant, plans, platform_admin, subscription (no demo data/users). Preview uses true
- Login page demo-account buttons hidden in prod build (empty REACT_APP_DEMO_* vars)
- Stripe live webhook registered; Stripe account still not activated for live charges (charges_enabled=false)
- 2026-09 Password show/hide eye toggle (components/PasswordInput.jsx) on Login, Signup (+invite accept), Settings password change; i18n show_password/hide_password. Deployed to prod (frontend only)
- Prod ¥100 live card payment test PASSED (INV-202609-0001 PAID via webhook). Test client payment-test@finora.co.jp still exists; refund/cleanup pending user decision
- 2026-09 One-click card refund: POST /api/stripe/refund/invoice/{iid} (admin_only, full refund of all un-refunded STRIPE payments, idempotency key per payment, marks payment refunded + refund_id, recompute excludes refunded, audit REFUND, notify client payment_refunded). Invoice list returns card_refundable (admin only). UI: RotateCcw button + AlertDialog in Billing InvoiceList, 返金済 badge in PaymentsList. Deployed to prod; real ¥100 refund of INV-202609-0001 succeeded (re_3UJZgtFtJwbFJjRZ1DFvcbPH). Invoice now back to ISSUED; test client payment-test@finora.co.jp still exists
- Not handled: refunds made directly in Stripe dashboard (no charge.refunded webhook sync), partial refunds
- 2026-09 Stripe-dashboard refund sync: webhook charge.refunded -> apply_refund (stripe_payments.py) idempotent cumulative refunded_amount (partial + full), recompute nets refunds, audit REFUND via Stripe, notify client. Live webhook now subscribes charge.refunded. Button refunds use same apply_refund
- 2026-09 Refund receipt email (email_service.py, Emergent managed email, from_name FINORA, reply-to tenant billing_profile.email, ja/en/pt by client user lang, sent to client login emails in background). Env: EMERGENT_EMAIL_KEY, EMAIL_FROM_NAME, PUBLIC_APP_URL (prod https://www.finora.co.jp). Verified send from VPS to delivered@resend.dev
- PENDING: prod end-to-end live test (user pays ¥100 on INV-202609-0001 via session in /root/finora_paytest.json 'session2', then ¥30 partial refund in Stripe dashboard). Test client email changed to ryuichi.kurozaki+paytest@gmail.com
- Note: preview demo client users (e.g. client@finora.co.jp) will receive real refund emails if refunds are simulated in preview
- 2026-09 BUG FIX (prod login failure): seed.upsert_user reset ADMIN password to .env ADMIN_PASSWORD on every backend restart, silently reverting the user's own password change. Now only resets when SEED_DEMO=true (preview demo). Deployed to prod, cleared lockout. Tested iteration_6 (100%). User must log in with issued pw and change it again
- 2026-09 Production public demo: isolated tenant finora-showcase (seed_showcase.py, env SEED_SHOWCASE=true in prod/false in preview), demo users demo-admin/consultant/client/client2@finora.co.jp pw FinoraDemo2026! (flag demo=True, platform_admin False). core.forbid_demo blocks credential/2FA/user/invite/billing-profile/Stripe/import/upload for demo users. Prod login shows one-click autofill buttons (build with REACT_APP_DEMO_* vars). Tested iteration_7 100%
- 2026-09 Sidebar: tenant admin (role admin) hides accounts, assets, transactions, portfolio, liabilities, cashflow, goals, analytics, risk, data_health, consulting, reports (Layout.jsx ADMIN_HIDDEN). Menu only; routes & ClientDetail tabs still accessible. Consultant/client unchanged. Deployed prod
- 2026-09 Signup consultants: /public/signup users get is_consultant=True (role stays admin = owner of own tenant; seed migrates existing signup-tenant owners). UI shows role label コンサルタント and full consultant menu (ADMIN_HIDDEN applies only to admins without is_consultant, e.g. FINORA own admin & demo-admin). Deployed prod (fianances.presage@gmail.com migrated). Frontend rsync now WITHOUT --delete to keep old chunks for open tabs
- 2026-09 Consultant scoping: core.sees_all(user) = admin without is_consultant. Signup consultants (is_consultant admins) now see/manage only clients where consultant_id/secondary == self (accessible_ids, scope, tasks visibility, client create/update/delete checks). FINORA own admin still sees whole tenant. Deployed prod
- 2026-09 Customer-count pricing: plans.base_fee + per_customer_fee (defaults 5000/500 paid plans, 0 FREE/TRIAL; editable in Platform > plans). Fee = (base + per × monthly PEAK customers) × months (db.customer_peaks via core.track_peak on client create & reads). /subscription returns pricing; Stripe SaaS checkout uses computed amount (409 if 0). Platform tenants list shows fee + peak. Client handover: POST /api/clients/reassign {from_id,to_id,client_ids} admin_only (is_consultant only from self); HandoverDialog on Clients page (hidden for demo). Deployed prod
- 2026-09 TWO-TIER E-CONTRACTS (econtract.py, econtract_tpl.py ja/en/pt templates, econtract_pdf.py reportlab + fonts/ipag.ttf). contract_type FINORA_SAAS (issuer=platform admin, recipient=tenant owner) / CONSULTING (issuer=client's consultant or sees_all admin, recipient=client). document_type FINORA_IMPORTANT_INFORMATION/FINORA_SERVICE_AGREEMENT/CONSULTING_IMPORTANT_INFORMATION/CONSULTING_AGREEMENT, numbers FS-/CC- (contracts), FIM/FAG/CIM/CAG (docs). Statuses DRAFT→IMPORTANT_INFO_SENT→IMPORTANT_INFO_CONFIRMED→CONTRACT_SENT→FIRST_PARTY_SIGNED(recipient)→BOTH_SIGNED(issuer)→ACTIVE; PAUSED/ENDED/CANCELLED. Docs frozen with SHA-256 at send; acts (VIEW/CONFIRM/SIGN with ip/ua/typed name/drawn PNG) in econtract_acts; audit entity econtracts. ACTIVE: PDFs to GridFS (B also into documents), A → tenant finora_contract ACTIVE + subscription ACTIVE; B → contracts doc ACTIVE (billing) + first invoice DRAFT; amendments = new version (parent ENDED AMENDED). A auto-started at signup (statement auto-sent; confirm auto-sends agreement). core.require_service gates client create/invitations/B create for tenants with finora_contract_required. End A stores end_policy (login blocked/read_only enforced at login). Legacy contracts ACTIVE/PAUSED → PAUSED needs_econtract; generic /data/contracts writes 403.
- UI: EContractPanel (ClientDetail contracts tab, Billing contracts tab, client /my-contracts nav 契約・重要事項, Settings FINORA契約 tab, Platform コンサルタント契約管理 tab), /econtracts/:id detail (stepper, confirm checkbox, SignaturePad, issuer tools, PDFs, versions, evidence). Banner when FINORA contract pending
- 2026-09 Sign-request notifications (sign_notify.py): on econtract_important_sent / agreement_sent / recipient_signed → email (Emergent managed, 3 langs, link PUBLIC_APP_URL/econtracts/:id) + WhatsApp via the server-shared Baileys service prc-whatsapp (pm2, /data/prc-time/whatsapp-service, POST http://127.0.0.1:8010/send {phone,message}; DO NOT modify it) when user whatsapp_phone + whatsapp_opt_in (Settings > 通知の受け取り, PUT /auth/preferences). env WHATSAPP_SERVICE_URL (prod http://127.0.0.1:8010, preview empty = skip). Delivery log db.message_log shown in contract evidence (issuer only)

## 2026-09 E-contract renewal/expiry reminders (更新期限のお知らせ)
- backend/renewal.py: hourly asyncio loop started on app startup (works on VPS, no external cron). Scans ACTIVE econtracts, sends at 30 days and 7 days before renew date to BOTH parties (FINORA_SAAS: platform admins + tenant admins; CONSULTING: consultant + client users)
- Renewal date (econtract.renew_on): end_date + auto_renew=false → end_date; end_date + auto_renew → end_date rolled forward yearly; no end_date + auto_renew → yearly anniversary of start_date; otherwise none
- Channels: in-app notification (kind econtract_renewal_notice) + email + WhatsApp (opt-in), JA/EN/PT; auto_renew wording = 更新のお知らせ, otherwise = 満了のお知らせ (re-contract suggestion). Logged in message_log
- Idempotent: db.renewal_notices unique key contract_id:renew_on:stage
- POST /api/econtracts/renewals/run?today=YYYY-MM-DD (platform admin only) for manual run / time-travel testing
- API rows expose renew_on / renew_days; EContractDetail shows amber badge (ec-renewal-badge) when ≤30 days + summary row 更新日／満了日
- iteration_13: backend 5/5, frontend pass. Deployed to prod (www.finora.co.jp)
- Deploy incident: backend rsync --delete wiped server venv (venv lives in backend/). Rebuilt venv with uv (pinned versions); ~1 min downtime. DEPLOY_VPS.md now excludes venv

## Backlog (current)
- P1: 2FA enforcement for logins, automated monthly invoice generation job
- P2: Staff management UI, configurable reminder days per tenant
- P3: bank/brokerage/market price API integrations
- 2026-09 Settings「データ連携」(CSV/Excel import/export) tab now admin-only (hidden for consultants; UI only, API unchanged per user choice). Deployed to prod (frontend)

## 2026-09 Consultant card payouts (manual transfer model)
- User choice: card payments for consultant invoices settle to FINORA Stripe account; FINORA manually transfers net to consultant bank. No FINORA commission; Stripe fee + bank transfer fee borne by consultant. Card-pay button hidden until tenant registers bank (default)
- backend/payouts.py: GET/PUT /api/payouts/bank (tenant admin; Fernet-encrypted tenants.payout_bank.enc; audit masked), GET /api/payouts (tenant pending + history), GET /api/platform/payouts, POST /api/platform/payouts/{tid} {transfer_fee, transfer_date, note} → db.payouts + payments.payout_settled, notify payout_sent
- Pending per payment = amount − refunded_amount − stripe_fee − payout_settled (refund after payout → negative carry-over). stripe_fee recorded at fulfillment from balance_transaction (fallback 3.6% estimate, flagged)
- checkout_invoice 409 without bank; invoice list card_enabled
- UI: Settings 請求者情報 tab → PayoutSettings (bank form + payout status); Platform → 送金管理 tab (PayoutsPanel)
- iteration_14: backend 22/22, frontend pass. Deployed to prod
- Note: FINORA holding client funds temporarily — user advised to confirm 収納代行 legal treatment

## 2026-09 Per-consultant payout accounts + client WhatsApp + account_number removal
- Payout bank moved from tenant to users.payout_bank (admin & consultant). Payee of a card payment = invoice client's consultant_id (fixed on payment as payee_id). /platform/payouts groups by payee; POST /platform/payouts/{user_id}
- Forced registration: PayoutGate modal (non-closable) for non-demo admin/consultant until bank registered (/auth/me payout_bank_registered). Settings tab 'payout_bank' for staff
- Card pay allowed only when the client's consultant has a bank (card_clients)
- Clients entity: whatsapp field (encrypted); sign_notify falls back to clients.whatsapp for client users without own WhatsApp number
- Accounts entity: account_number removed from UI/API; startup migration unsets existing values
- iteration_15: backend 26/26; UI bug (save button hidden in gate) fixed & verified. Deployed to prod

## 2026-09 Client invitation delivery (email + WhatsApp)
- 顧客一覧 invite dialog now really sends the invite link by email (Emergent email) + WhatsApp (local service) — previously link-only (MOCKED note removed)
- WhatsApp number prefilled from clients.whatsapp; stored encrypted on invitation (+ whatsapp_masked); delivery status per channel saved on invitation.delivery
- POST /api/invitations/{id}/resend (PENDING/EXPIRED): new token, +7 days, resend both channels
- sign_notify.wa_digits normalizes numbers (JP leading 0 → 81)
- iteration_16: backend 6/6, frontend pass. Deployed to prod
- 2026-09 WhatsApp invite icon: 顧客一覧 actions have green WhatsApp icon → WhatsApp-only invite (channel=whatsapp, email optional; client enters own email on /invite accept). Delivery shown as mail/WhatsApp icon badges. Self-tested (curl + screenshots). Deployed to prod

## WhatsApp decision (user, 2026-09) — UPDATED: now uses JWSEA Foundation's WhatsApp
- FINORA sends WhatsApp via JWSEA server (160.251.123.166, ssh port 10022, key /root/.ssh/jwsea_vps.pem in preview pod) service jwsea-wa (systemd, /data/jwsea/wa-notify, 127.0.0.1:3100, sender +81 70-9460-8789 'システム配信専用'). API: POST /send {to, message} → 200 {ok:true}; 422 not_registered_on_whatsapp; 503 not_connected; GET /status
- Bridge: FINORA VPS systemd 'finora-wa-tunnel' (ssh -L 127.0.0.1:3101 → JWSEA 127.0.0.1:3100) with key /root/.ssh/jwsea_wa_tunnel on FINORA VPS; JWSEA authorized_keys entry restricted (restrict,port-forwarding,permitopen=127.0.0.1:3100,command=/bin/false). Prod .env WHATSAPP_SERVICE_URL=http://127.0.0.1:3101
- PRC Time WhatsApp service (8010) no longer used by FINORA (user choice). Do not modify JWSEA/PRC services
- Test message sent 2026-09-26 to +81 90-3938-7570 OK
- Open security risk (not fixed, awaiting user approval): https://prc-time.jp/whatsapp/ (nginx proxy to 8010) is public without auth → /send, /send-bulk, /disconnect, /qr callable by anyone. Fix must not break PRC Time frontend

## 2026-09 WhatsApp health alert + invoice issue notifications + invite auto-reminders
- backend/wa_health.py: 5-min probe of {WHATSAPP_SERVICE_URL}/status; down after 2 consecutive failures; emails platform admins on down / recovery; GET /api/system/wa-health (role admin; detail only for platform admin). db.system_state {id:'wa_health'}
- Frontend WaHealthBanner (red) for non-demo role=admin (platform admin + tenant admins)
- backend/invoice_notify.py: on POST /invoices/{id}/issue → email + WhatsApp to client users (or client record contact); card wording if client in card_clients else bank-transfer; stored invoices.issue_delivery
- tenancy.remind_scan: PENDING invites auto-resent at +3d and +6d after created_at (max 2), new token, +7d expiry, reminders_sent/last_reminded_at; runs in hourly renewal.loop; POST /api/invitations/reminders/run?at= (platform admin). tz-naive dates handled (_utc)
- sign_notify.wa_send helper; email body white-space:pre-line
- Preview .env WHATSAPP_SERVICE_URL=http://127.0.0.1:3999 (intentionally unreachable; system_state seeded down to avoid alert emails)
- iteration_17: backend 8/8, frontend pass; tz bug fixed & verified. Deployed to prod (prod wa_health ok)

## 2026-09 Language unification (JA/EN/PT)
- Fixed i18n key collisions (ALL = {...D,...L,...F,...B} later files overrode): billing balance→inv_balance, issue→inv_issue, fee→contract_fee; features current_value→goal_current_value, internal/shared→vis_internal/vis_shared (entities visibility prefix "vis_"); landing ai_title→landing_ai_title; removed dict 'platform' dup and features close/target dups
- New keys: REFUNDED/SENT/SIGNED/FAILED/SKIPPED, welcome_prefix/suffix, months_unit, years_later, premium_plan, required_suffix, import_errors; hardcoded strings replaced
- Backend: all HTTPException details English-only in code; backend/i18n_errors.py translates by X-Lang header (frontend api.js sends finora_lang); RequestValidationError → single localized string. Mixed "日本語 (English)" messages removed
- Audit tool: node /root/tools/i18n_audit.mjs (DUP KEYS / MISSING KEYS / hardcoded text). Keep DUP KEYS = 0 when adding keys
- iteration_18: backend 17/17, frontend pass. Deployed to prod

## 2026-09 E-contract documents shown in the viewer's language
- GET /api/econtracts/{cid}?view_lang=ja|en|pt → when different from the contract's document language, returns `view` {lang, original_lang, important/agreement: {title, sections}} built from templates (econtract._translated; doc_date from issued doc). Consultant free-text fields stay as written
- Signed original (hash, PDF) unchanged and authoritative; UI shows "参考訳（正本は○○語版）" note + toggle 正本を表示/参考訳を表示 (EContractDetail DocView)
- Self-tested (curl + screenshots EN/PT/JA). Deployed to prod

## 2026-09 Client self-service portfolio entry + ticker lookup
- Portfolio page: client users see EntityManager(assets) section 'portfolio-holdings-entry' (add/edit/delete own holdings; refreshes KPIs/charts/holdings table). Staff unchanged (read-only on client-owned data by design)
- backend/quote.py: GET /api/quote?ticker= (yfinance / Yahoo Finance, no key, 10-min cache) → name, price, currency, country (.T→JP, .SA→BR, none→US), price_date. Errors localized (i18n_errors). yfinance==1.7.0 installed in prod venv via uv
- EntityManager TickerLookup (entities assets ticker lookup:true) fills name (if empty), current_price, currency, price_date, country
- iteration_19: backend 8/8, frontend pass. Deployed to prod

## 2026-09 Corporate public website + CMS
- Public pages (no login): / (landing + LatestNews + company card), /company (CEO message, overview, history, access), /services, /news (+category filter), /news/:id, /faq, /contact. Shared nav (Chrome.jsx NavLink; testids landing-link-*, landing-mlink-*, footer-link-*) + footer with CMS company info & social links
- backend/site_cms.py: db.site_settings {id:'main', data:{field: {ja,en,pt} | plain}}, db.site_items {kind service|news|faq|history, title/body {ja,en,pt}, date, category (news: notice|press|media|event), image, order, published}. Public GET /api/public/site, /site/news, /site/news/{id}, /site/files/{name}; admin (platform_admin) GET /api/platform/site, PUT settings, CRUD items, POST upload (png/jpg/webp/gif ≤5MB → SITE_UPLOAD_DIR). seed_site() placeholder content once
- Admin UI: Platform → 公開サイト tab (components/SiteAdmin.jsx)
- Inquiry email to SITE_INQUIRY_EMAIL=info@finora.co.jp — currently UNDELIVERABLE (finora.co.jp has no MX record); inquiries still saved (Settings → inquiries)
- Env: SITE_UPLOAD_DIR (preview /app/backend/site_uploads, prod /data/finora-saas/site-uploads), SITE_INQUIRY_EMAIL. Deploy rsync must --exclude site_uploads
- iteration_20: backend 14/14, frontend pass; dup testids fixed. Deployed to prod
- 2026-09 Operator info set (preview + prod DB via /root/tools/prc_company.py): PRC Remit株式会社, 代表 黒崎 龍一, 〒514-0011 三重県津市高洲町23番25号, 設立 2026-05-22, 資本金100万円, TEL 059-212-0393, 事業内容 from prcremit.co.jp/company; history 2026-05 設立. CEO message body & email still placeholder/empty (not published on their site). Corporate number 7190001033156

## 2026-09 Email switched to own SMTP (no per-message cost)
- email_service.send_email now uses the VPS Postfix (127.0.0.1:25, OpenDKIM signs *@prcremit.co.jp, SPF mx, DMARC p=none). From "FINORA <finora@prcremit.co.jp>", Reply-To info@prcremit.co.jp (finora@ has NO mailbox yet). Emergent managed email no longer used
- Env: EMAIL_TRANSPORT (prod smtp, preview log → db.email_log only, nothing sent), EMAIL_FROM, EMAIL_REPLY_TO, SMTP_HOST, SMTP_PORT; SITE_INQUIRY_EMAIL=info@prcremit.co.jp (prod & preview)
- Verified on prod: test mail to Gmail accepted (250 OK) and to info@prcremit.co.jp delivered to maildir

## 2026-09 finora@ mailbox + Email delivery log
- PROD VPS: created real mailbox finora@prcremit.co.jp (/etc/postfix/vmailbox + postmap, /etc/dovecot/users SHA512-CRYPT, Maildir /var/mail/vhosts/prcremit.co.jp/finora, backups *.bak-<ts>). IMAP mail.prcremit.co.jp:993 SSL login verified; test delivery OK. Password in /root/finora_prod_secrets.txt. Reply-To still info@prcremit.co.jp (unchanged)
- backend/mail_log.py: send_email(kind=...) records db.email_log {id,to,subject,kind,message_id,queue_id,status queued|delivered|deferred|bounced|failed|logged,detail,at,updated_at}. 2-min loop parses Postfix log MAIL_LOG_PATH incrementally (offset+inode in system_state id='mail_log', handles logrotate .1 & truncation): cleanup message-id → queue_id, smtp/virtual status=sent/deferred/bounced, qmgr expired → bounced
- API (platform admin only): GET /api/platform/email-log?q&kind&status&skip&limit, POST /api/platform/email-log/sync
- UI: Platform → メール送信ログ tab (EmailLogPanel.jsx): search to/subject, kind select, status chips with counts, pagination, sync button. Platform TabsList now wraps on mobile
- Env: MAIL_LOG_PATH (preview /tmp/finora_mail.log fake file; prod should be /var/log/mail.log — backend runs as root)
- iteration_21: backend 10/10, frontend pass (mobile tab wrap fixed & verified)
- DEPLOYED to prod 2026-09-26: prod .env MAIL_LOG_PATH=/var/log/mail.log (backup .env.bak-<ts>), backend rsync (venv kept) + restart, frontend build rsync. Verified: test mail to finora@ → log status delivered (dsn=2.0.0), Platform tab renders on www.finora.co.jp
- 2026-09-26 BUG FIX: public nav/footer "料金プラン" (/#pricing) from other pages landed at top of home. Cause: plain <a> full reload, browser anchor scroll ran before SPA rendered #pricing. Fix: Chrome.jsx NavLink always router Link; Landing.jsx useHashScroll (polls for hash element, scrolls with 72px nav offset). Verified preview + prod (desktop, mobile menu, footer, direct /#pricing). Deployed prod (frontend)
- 2026-09-26 Nav label 会社情報 → 会社概要 (nav_company ja). FINORA_SAAS e-contract issuer (事業者名/甲/連絡先) now read from public-site 会社概要 (site_settings main: company_name, representative (+代表取締役 prefix if no title), address, corporate_number (new plain field, SiteAdmin input sa-corporate_number), phone/email) in the contract language (econtract._site_issuer); falls back to platform tenant billing_profile. POST /api/econtracts/{cid}/reissue (issuer; status IMPORTANT_INFO_SENT→important doc, CONTRACT_SENT→agreement doc): new doc number/hash, old doc superseded_by (kept), audit REISSUE; UI button ec-reissue with confirm; EContractDetail ignores superseded docs. Prod: corporate_number set 7190001033156; FS-00001→FIM-00003, FS-00002→FIM-00004 reissued (no re-notification sent). Deployed prod
- 2026-09-26 FINORA_SAAS service name default "FINORA" → "FINORA SaaS" (econtract.start_finora_contract + EContractForm default). Prod: FS-00001/FS-00002 terms updated & reissued → FIM-00005 / FIM-00006. Deployed prod
- 2026-09-26 follow-up: after /#pricing, clicking ホーム/logo ("/") didn't scroll up (same route). useHashScroll now depends on location.key and scrolls to top when no hash. Verified preview; deployed prod
