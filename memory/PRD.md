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

## Backlog
- P0: 2FA (TOTP)
- P1: LLM plug-in for AI engine (optional, paid), market price / FX API sync, email deadline notifications (cron)
- P1: meeting-minutes AI summarization, per-tenant risk threshold settings
- P2: accounting system / bank API integration, backup UI, multi-tenant signup
