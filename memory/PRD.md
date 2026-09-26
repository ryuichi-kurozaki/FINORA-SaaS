# FINORA — PRD

## Original Problem Statement
FINORA 投資管理コンサルティングSaaS（www.finora.co.jp）。個人・法人の資産／投資／負債／キャッシュフロー／金融口座を一元管理し、AI分析・リスク管理・将来シミュレーション・コンサルティング支援を行う。デザイン「Premium FinTech × Near Future」、ブランドカラー Midnight Navy #071A2B / Emerald #00A878 / Gold #C9A227。ロール：管理者・コンサルタント・顧客。Phase 1〜8 の順で開発。

## User Choices
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
