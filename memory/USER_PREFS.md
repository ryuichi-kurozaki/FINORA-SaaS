# User preferences (MUST follow)
- ALL messages, reports, questions AND finish-tool summaries — including "Next Action Items" titles and lines — must be written in Japanese. No English text in user-facing output.
- NEVER proactively suggest, offer, or nudge deployment/publishing (公開無料 / Deploy / 本番反映 / redeploy). Do NOT add "本番へデプロイ" to Next Action Items. Only deploy when the user EXPLICITLY commands it in that message. (User strongly insisted 2026-06.)
- DEPLOYMENT METHOD = direct SSH to the user's own VPS (production = finora.co.jp, 160.251.120.127). DO NOT use Emergent's deployer / "公開無料" button — the user does NOT use it and gets upset when it is suggested or triggered. Deploy by SSH'ing to the VPS with the user-provided .pem key and updating the code + restarting services there.
