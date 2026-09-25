"""FINORA AI Intelligence - deterministic rule engine (no external LLM cost). Swap `ENGINE` to plug an LLM later."""
import re
from datetime import datetime, timedelta

from analytics import simulate

ENGINE = "finora-rule-engine-v1"


def tr(lang, ja, en, pt):
    return {"ja": ja, "en": en, "pt": pt}.get(lang, ja)


def yen(v):
    return f"¥{v:,.0f}"


def pct(v):
    return f"{v:+.1f}%"


RISK_NAMES = {
    "concentration": ("集中投資", "Concentration", "Concentração"),
    "currency": ("通貨リスク", "Currency risk", "Risco cambial"),
    "country": ("国別リスク", "Country risk", "Risco-país"),
    "sector": ("業種リスク", "Sector risk", "Risco setorial"),
    "interest_rate": ("金利リスク", "Interest-rate risk", "Risco de juros"),
    "liquidity": ("流動性リスク", "Liquidity risk", "Risco de liquidez"),
    "leverage": ("借入比率", "Leverage ratio", "Alavancagem"),
    "balance": ("資産／負債バランス", "Asset/Liability balance", "Equilíbrio ativo/passivo"),
}
ADVICE = {
    "concentration": ("単一資産への集中度が高いため、段階的な分散（リバランス）を検討する余地があります。",
                      "Exposure to a single holding is high; a phased rebalancing could reduce concentration.",
                      "A exposição a um único ativo é alta; um rebalanceamento gradual pode reduzir a concentração."),
    "currency": ("外貨建て資産の比率が高く、為替変動が純資産に大きく影響します。為替ヘッジや円資産比率の見直しが論点です。",
                 "Foreign-currency exposure is high; FX moves strongly affect net worth. Consider hedging or rebalancing to JPY.",
                 "A exposição em moeda estrangeira é alta; considere hedge cambial ou rebalanceamento."),
    "country": ("特定国への投資集中が見られます。地域分散の検討が推奨されます。",
                "Investments are concentrated in one country; geographic diversification is recommended.",
                "Os investimentos estão concentrados em um país; recomenda-se diversificação geográfica."),
    "sector": ("株式の業種偏りが大きく、特定業種の不調時の下落幅が拡大する可能性があります。",
               "Equity holdings are skewed to one sector, increasing downside in a sector downturn.",
               "As ações estão concentradas em um setor, aumentando o risco de queda."),
    "interest_rate": ("変動金利負債の比率が高く、金利上昇時に返済負担が増加します。固定化・繰上返済の比較検討が論点です。",
                      "A large share of debt is variable-rate; rising rates would increase repayments. Compare fixing vs. prepayment.",
                      "Grande parte da dívida é pós-fixada; compare taxa fixa ou amortização antecipada."),
    "liquidity": ("生活費に対する流動資金が不足気味です。最低6ヶ月分の緊急資金確保を推奨します。",
                  "Liquid funds are thin relative to expenses; keep at least 6 months as an emergency reserve.",
                  "A liquidez é baixa frente às despesas; mantenha reserva de pelo menos 6 meses."),
    "leverage": ("総資産に対する借入比率が高水準です。返済計画と資産売却余力の確認が必要です。",
                 "Debt relative to assets is high; review the repayment plan and liquidation capacity.",
                 "A dívida em relação aos ativos é alta; revise o plano de pagamento."),
    "balance": ("資産と負債のバランスが脆弱です。資産価格下落時の債務超過リスクに留意してください。",
                "The asset/liability buffer is thin; watch for negative equity if asset prices fall.",
                "A margem entre ativos e passivos é estreita; atenção ao risco de patrimônio negativo."),
}


def item(typ, severity, text):
    return {"type": typ, "severity": severity, "text": text}


def risk_text(lang, r):
    n = RISK_NAMES[r["code"]][("ja", "en", "pt").index(lang) if lang in ("ja", "en", "pt") else 0]
    unit = {"months": tr(lang, "ヶ月", " months", " meses"), "x": "x"}.get(r["unit"], "%")
    th = r["danger"] if r["level"] == "danger" else r["warn"]
    cmp = "<" if r["reverse"] else ">"
    return f"{n}: {r['value']}{unit} ({tr(lang, '基準', 'threshold', 'limite')} {cmp} {th}{unit})"


def snap_at(series, date_str):
    ym = date_str[:7]
    cands = [s for s in series if s["date"] <= ym]
    return cands[-1] if cands else (series[0] if series else None)


def change_line(lang, prev, cur, label):
    if not prev or not cur or not prev["net_worth"]:
        return None
    d = cur["net_worth"] - prev["net_worth"]
    p = d / abs(prev["net_worth"]) * 100
    return item("calc", "ok" if d >= 0 else "warn",
                tr(lang, f"{label}（{prev['date']}）比で純資産が {yen(d)}（{pct(p)}）変化",
                   f"Net worth changed by {yen(d)} ({pct(p)}) vs {label} ({prev['date']})",
                   f"Patrimônio líquido variou {yen(d)} ({pct(p)}) vs {label} ({prev['date']})"))


def insights(ctx, lang="ja"):
    s, cf, rk, series, data = ctx["summary"], ctx["cashflow"], ctx["risk"], ctx["trend"], ctx["data"]
    today = datetime.now().date().isoformat()
    cur = series[-1] if series else None
    out = {"changes": [], "risks": [], "checks": [], "since_last": [], "missing": [], "summary": []}
    out["changes"].append(item("fact", "info", tr(lang,
        f"総資産 {yen(s['total_assets'])}／総負債 {yen(s['total_liabilities'])}／純資産 {yen(s['net_worth'])}",
        f"Total assets {yen(s['total_assets'])} / liabilities {yen(s['total_liabilities'])} / net worth {yen(s['net_worth'])}",
        f"Ativos {yen(s['total_assets'])} / passivos {yen(s['total_liabilities'])} / patrimônio {yen(s['net_worth'])}")))
    if len(series) >= 2:
        out["changes"].append(change_line(lang, series[-2], cur, tr(lang, "前月", "last month", "mês anterior")))
    if len(series) >= 13:
        out["changes"].append(change_line(lang, series[-13], cur, tr(lang, "前年同月", "a year ago", "um ano atrás")))
    if s["principal"]:
        out["changes"].append(item("calc", "ok" if s["unrealized_pl"] >= 0 else "danger", tr(lang,
            f"投資元本 {yen(s['principal'])} に対し含み損益 {yen(s['unrealized_pl'])}（{pct(s['unrealized_pct'])}）",
            f"Unrealized P/L {yen(s['unrealized_pl'])} ({pct(s['unrealized_pct'])}) on principal {yen(s['principal'])}",
            f"Lucro não realizado {yen(s['unrealized_pl'])} ({pct(s['unrealized_pct'])}) sobre {yen(s['principal'])}")))
    for a in data["assets"]:
        if a.get("acquisition_total") and (a["unrealized_pct"] > 80 or a["unrealized_pct"] < -30):
            out["changes"].append(item("estimate", "warn", tr(lang,
                f"異常値検出：{a.get('name')} の損益率 {pct(a['unrealized_pct'])}（価格入力誤り or 大幅変動の可能性）",
                f"Anomaly: {a.get('name')} P/L {pct(a['unrealized_pct'])} (possible input error or large move)",
                f"Anomalia: {a.get('name')} com variação {pct(a['unrealized_pct'])} (possível erro ou forte oscilação)")))
    for r in rk["alerts"]:
        out["risks"].append(item("calc", r["level"], risk_text(lang, r)))
    if cf["cf_m"] < 0:
        out["risks"].append(item("calc", "danger", tr(lang, f"月間キャッシュフローが赤字です（{yen(cf['cf_m'])}）",
                                                      f"Monthly cash flow is negative ({yen(cf['cf_m'])})",
                                                      f"Fluxo de caixa mensal negativo ({yen(cf['cf_m'])})")))
    soon = (datetime.now() + timedelta(days=14)).date().isoformat()
    for t in data["tasks"]:
        if t.get("status") != "done" and t.get("due_date"):
            if t["due_date"] < today:
                out["checks"].append(item("fact", "danger", tr(lang, f"期限超過：{t['title']}（{t['due_date']}）",
                                                               f"Overdue: {t['title']} ({t['due_date']})",
                                                               f"Atrasado: {t['title']} ({t['due_date']})")))
            elif t["due_date"] <= soon:
                out["checks"].append(item("fact", "warn", tr(lang, f"期限間近：{t['title']}（{t['due_date']}）",
                                                             f"Due soon: {t['title']} ({t['due_date']})",
                                                             f"Vence em breve: {t['title']} ({t['due_date']})")))
    year = (datetime.now() + timedelta(days=365)).date().isoformat()
    for l in data["liabilities"]:
        if l.get("maturity_date") and today <= l["maturity_date"] <= year:
            out["checks"].append(item("fact", "warn", tr(lang, f"1年以内に満期：{l.get('institution')}（{l['maturity_date']}）",
                                                         f"Matures within 1 year: {l.get('institution')} ({l['maturity_date']})",
                                                         f"Vence em 1 ano: {l.get('institution')} ({l['maturity_date']})")))
    for c in data["consulting"]:
        if c.get("next_action") and c.get("status") != "done":
            out["checks"].append(item("fact", "info", tr(lang, f"次回対応：{c['next_action']}", f"Next action: {c['next_action']}",
                                                         f"Próxima ação: {c['next_action']}")))
    lm = ctx.get("last_meeting")
    if lm and series:
        line = change_line(lang, snap_at(series, lm), cur, tr(lang, "前回面談", "last meeting", "última reunião"))
        if line:
            out["since_last"].append(line)
        prev = snap_at(series, lm)
        if prev and prev["total_liabilities"]:
            d = cur["total_liabilities"] - prev["total_liabilities"]
            out["since_last"].append(item("calc", "info", tr(lang, f"負債残高の変化：{yen(d)}", f"Change in liabilities: {yen(d)}",
                                                             f"Variação dos passivos: {yen(d)}")))
    elif not lm:
        out["since_last"].append(item("fact", "info", tr(lang, "面談記録がありません", "No meeting records yet", "Sem registros de reunião")))
    miss_price = [a for a in data["assets"] if not a.get("current_price")]
    if miss_price:
        out["missing"].append(item("fact", "warn", tr(lang, f"現在価格が未入力の資産：{len(miss_price)}件",
                                                      f"Assets without current price: {len(miss_price)}",
                                                      f"Ativos sem preço atual: {len(miss_price)}")))
    no_acct = [a for a in data["assets"] if not a.get("account_id") and a.get("asset_class") not in ("real_estate", "cash")]
    if no_acct:
        out["missing"].append(item("fact", "info", tr(lang, f"口座未紐付けの資産：{len(no_acct)}件", f"Assets not linked to an account: {len(no_acct)}",
                                                      f"Ativos sem conta vinculada: {len(no_acct)}")))
    for c in data["clients"]:
        if not c.get("risk_tolerance"):
            out["missing"].append(item("fact", "warn", tr(lang, f"リスク許容度未設定：{c.get('name')}", f"Risk tolerance not set: {c.get('name')}",
                                                          f"Tolerância a risco não definida: {c.get('name')}")))
    if not data["cashflows"]:
        out["missing"].append(item("fact", "warn", tr(lang, "キャッシュフローが未登録です", "No cash-flow data registered", "Nenhum fluxo de caixa cadastrado")))
    out["summary"] = ai_summary(ctx, lang)
    for k in out:
        out[k] = [x for x in out[k] if x]
    return out


def ai_summary(ctx, lang):
    s, rk, m, cf = ctx["summary"], ctx["risk"], ctx["metrics"], ctx["cashflow"]
    li = ("ja", "en", "pt").index(lang) if lang in ("ja", "en", "pt") else 0
    lines = [item("ai", "ok" if rk["score"] >= 75 else "warn" if rk["score"] >= 50 else "danger", tr(lang,
        f"総合リスクスコアは {rk['score']}/100。" + ("全体として健全な資産構成です。" if rk["score"] >= 75 else "いくつかの改善余地があります。" if rk["score"] >= 50 else "優先的に対処すべきリスクがあります。"),
        f"Overall risk score {rk['score']}/100. " + ("The structure is broadly healthy." if rk["score"] >= 75 else "There is room for improvement." if rk["score"] >= 50 else "Some risks need priority action."),
        f"Pontuação de risco {rk['score']}/100. " + ("Estrutura saudável." if rk["score"] >= 75 else "Há espaço para melhorias." if rk["score"] >= 50 else "Há riscos que exigem ação prioritária.")))]
    if m.get("annual_return_pct") is not None:
        lines.append(item("estimate", "info", tr(lang,
            f"過去{m['months']}ヶ月の推定年率リターン {pct(m['annual_return_pct'])}（参考ベンチマーク {pct(m['benchmark_return_pct'])}）、ボラティリティ {m['volatility_pct']:.1f}%",
            f"Estimated annualized return over {m['months']} months {pct(m['annual_return_pct'])} (benchmark {pct(m['benchmark_return_pct'])}), volatility {m['volatility_pct']:.1f}%",
            f"Retorno anualizado estimado em {m['months']} meses {pct(m['annual_return_pct'])} (benchmark {pct(m['benchmark_return_pct'])}), volatilidade {m['volatility_pct']:.1f}%")))
    for r in sorted(rk["alerts"], key=lambda x: x["level"] != "danger")[:3]:
        lines.append(item("ai", r["level"], ADVICE[r["code"]][li]))
    if cf["investable_m"] > 0:
        lines.append(item("ai", "ok", tr(lang, f"月あたり約 {yen(cf['investable_m'])} の投資可能資金があり、積立投資による資産形成余地があります。",
                                         f"About {yen(cf['investable_m'])}/month is investable, leaving room for regular investing.",
                                         f"Cerca de {yen(cf['investable_m'])}/mês está disponível para investimentos regulares.")))
    return lines


INTENTS = [
    ("report", ["レポート", "報告", "report", "relatório", "relatorio"]),
    ("change", ["変わ", "変化", "前回", "change", "since", "mudou", "mudança", "desde"]),
    ("risk", ["リスク", "risk", "risco"]),
    ("cashflow", ["キャッシュ", "収支", "cash", "fluxo", "caixa"]),
    ("projection", ["推移", "将来", "年後", "年間", "future", "projection", "years", "futuro", "projeção", "anos"]),
]


def detect(q):
    ql = q.lower()
    for name, kws in INTENTS:
        if any(k in ql for k in kws):
            return name
    return "overview"


def sec(label, title, lines):
    return {"label": label, "title": title, "lines": [l for l in lines if l]}


def ans_overview(ctx, lang):
    s, b = ctx["summary"], ctx["breakdowns"]
    top = ", ".join(f"{x['key']} {x['pct']}%" for x in b["asset_class"][:4])
    return [
        sec("fact", tr(lang, "登録データ（事実）", "Registered data (facts)", "Dados registrados (fatos)"), [
            tr(lang, f"資産 {s['asset_count']}件／負債 {s['liability_count']}件", f"{s['asset_count']} assets / {s['liability_count']} liabilities",
               f"{s['asset_count']} ativos / {s['liability_count']} passivos"),
            tr(lang, f"資産クラス構成：{top}", f"Asset-class mix: {top}", f"Composição: {top}")]),
        sec("calc", tr(lang, "計算結果", "Calculations", "Cálculos"), [
            f"{tr(lang, '総資産', 'Total assets', 'Ativos totais')}: {yen(s['total_assets'])}",
            f"{tr(lang, '総負債', 'Total liabilities', 'Passivos totais')}: {yen(s['total_liabilities'])}",
            f"{tr(lang, '純資産', 'Net worth', 'Patrimônio líquido')}: {yen(s['net_worth'])}",
            f"{tr(lang, '含み損益', 'Unrealized P/L', 'Lucro não realizado')}: {yen(s['unrealized_pl'])} ({pct(s['unrealized_pct'])})",
            f"{tr(lang, '年間配当・利息', 'Annual dividends & interest', 'Dividendos e juros anuais')}: {yen(s['dividends'] + s['interest'])}"]),
        sec("ai", tr(lang, "AIによる分析", "AI analysis", "Análise da IA"), [x["text"] for x in ai_summary(ctx, lang)]),
    ]


def ans_change(ctx, lang):
    ins = insights(ctx, lang)
    lm = ctx.get("last_meeting")
    return [
        sec("fact", tr(lang, "前回面談", "Last meeting", "Última reunião"),
            [lm or tr(lang, "面談記録なし", "No meeting recorded", "Sem reunião registrada")]),
        sec("calc", tr(lang, "変化（計算結果）", "Changes (calculated)", "Mudanças (calculadas)"),
            [x["text"] for x in ins["since_last"] + ins["changes"][1:3]]),
        sec("ai", tr(lang, "AIによる分析", "AI analysis", "Análise da IA"), [x["text"] for x in ins["summary"][:2]]),
    ]


def ans_risk(ctx, lang):
    rk = ctx["risk"]
    li = ("ja", "en", "pt").index(lang) if lang in ("ja", "en", "pt") else 0
    return [
        sec("calc", tr(lang, "リスク指標（計算結果）", "Risk metrics (calculated)", "Métricas de risco (calculadas)"),
            [f"[{r['level'].upper()}] " + risk_text(lang, r) for r in rk["items"]]),
        sec("ai", tr(lang, "主要リスクと示唆", "Key risks & implications", "Principais riscos"),
            [ADVICE[r["code"]][li] for r in rk["alerts"]] or [tr(lang, "閾値を超える重大リスクは検出されませんでした。", "No risk exceeded its threshold.", "Nenhum risco excedeu o limite.")]),
    ]


def ans_cashflow(ctx, lang):
    cf = ctx["cashflow"]
    return [
        sec("fact", tr(lang, "主な収入・支出（月額換算）", "Main income & expenses (monthly)", "Principais receitas e despesas (mensal)"),
            [f"+ {x['key']}: {yen(x['value'])}" for x in cf["income_by"][:4]] + [f"- {x['key']}: {yen(x['value'])}" for x in cf["expense_by"][:5]]),
        sec("calc", tr(lang, "計算結果", "Calculations", "Cálculos"), [
            f"{tr(lang, '月間CF', 'Monthly CF', 'FC mensal')}: {yen(cf['cf_m'])}",
            f"{tr(lang, '年間CF', 'Annual CF', 'FC anual')}: {yen(cf['cf_y'])}",
            f"{tr(lang, '自由資金', 'Free cash', 'Caixa livre')}: {yen(cf['free_m'])}"]),
        sec("estimate", tr(lang, "推定", "Estimate", "Estimativa"), [
            tr(lang, f"投資可能資金（収入の10%を予備費として控除）：月 {yen(cf['investable_m'])}",
               f"Investable funds (10% of income kept as buffer): {yen(cf['investable_m'])}/month",
               f"Recursos investíveis (10% da renda como reserva): {yen(cf['investable_m'])}/mês")]),
        sec("ai", tr(lang, "AIによる分析", "AI analysis", "Análise da IA"), [
            tr(lang, "収支は黒字で、積立余力があります。" if cf["cf_m"] >= 0 else "収支が赤字のため、支出構造の見直しが優先課題です。",
               "Cash flow is positive with room for saving." if cf["cf_m"] >= 0 else "Cash flow is negative; reviewing expenses is the priority.",
               "Fluxo positivo, com espaço para poupança." if cf["cf_m"] >= 0 else "Fluxo negativo; revisar despesas é prioridade.")]),
    ]


def ans_projection(ctx, lang, years):
    sim = simulate(ctx["summary"], ctx["cashflow"], ctx["data"]["liabilities"], {"years": years})
    r = sim["rows"][-1]
    return [
        sec("fact", tr(lang, "前提条件", "Assumptions", "Premissas"), [
            tr(lang, f"期間 {years}年／毎月積立 {yen(sim['contribution_m'])}／配当再投資あり",
               f"{years} years / monthly contribution {yen(sim['contribution_m'])} / dividends reinvested",
               f"{years} anos / aporte mensal {yen(sim['contribution_m'])} / dividendos reinvestidos"),
            tr(lang, "想定年率：強気 8%／標準 5%／弱気 1%", "Assumed returns: bull 8% / base 5% / bear 1%", "Retornos: otimista 8% / base 5% / pessimista 1%")]),
        sec("estimate", tr(lang, f"{years}年後の純資産（推定）", f"Net worth in {years} years (estimate)", f"Patrimônio em {years} anos (estimativa)"), [
            f"{tr(lang, '強気', 'Bull', 'Otimista')}: {yen(r['bull'])}", f"{tr(lang, '標準', 'Base', 'Base')}: {yen(r['base'])}",
            f"{tr(lang, '弱気', 'Bear', 'Pessimista')}: {yen(r['bear'])}", f"{tr(lang, '負債残高', 'Remaining debt', 'Dívida restante')}: {yen(r['debt'])}"]),
        sec("ai", tr(lang, "AIによる分析", "AI analysis", "Análise da IA"), [
            tr(lang, f"標準シナリオでは純資産は現在の {yen(sim['start_net_worth'])} から {yen(r['base'])} へ推移する見込みです。弱気シナリオとの差 {yen(r['base'] - r['bear'])} が不確実性の幅です。",
               f"In the base case net worth moves from {yen(sim['start_net_worth'])} to {yen(r['base'])}. The gap to the bear case ({yen(r['base'] - r['bear'])}) shows the uncertainty range.",
               f"No cenário base o patrimônio vai de {yen(sim['start_net_worth'])} para {yen(r['base'])}. A diferença para o pessimista ({yen(r['base'] - r['bear'])}) indica a incerteza.")]),
    ]


def ans_report(ctx, lang):
    name = ", ".join(c.get("corporate_name") or c.get("name") or "" for c in ctx["data"]["clients"][:3])
    head = sec("fact", tr(lang, "顧客説明用レポート", "Client report", "Relatório ao cliente"), [
        tr(lang, f"対象：{name}", f"Client: {name}", f"Cliente: {name}"),
        tr(lang, f"作成日：{datetime.now().date().isoformat()}", f"Date: {datetime.now().date().isoformat()}", f"Data: {datetime.now().date().isoformat()}")])
    body = ans_overview(ctx, lang)[1:2] + ans_cashflow(ctx, lang)[1:2] + ans_risk(ctx, lang) + ans_projection(ctx, lang, 10)[1:]
    disclaimer = sec("fact", tr(lang, "留意事項", "Disclaimer", "Aviso"), [tr(lang,
        "本レポートは登録データに基づく分析であり、将来の運用成果を保証するものではありません。",
        "This report is based on registered data and does not guarantee future results.",
        "Este relatório baseia-se nos dados registrados e não garante resultados futuros.")])
    return [head] + body + [disclaimer]


def ask(ctx, lang, question):
    intent = detect(question)
    if intent == "projection":
        m = re.search(r"(\d{1,2})", question)
        years = max(1, min(40, int(m.group(1)))) if m else 10
        sections = ans_projection(ctx, lang, years)
    else:
        sections = {"overview": ans_overview, "change": ans_change, "risk": ans_risk, "cashflow": ans_cashflow,
                    "report": ans_report}[intent](ctx, lang)
    return {"intent": intent, "engine": ENGINE, "sections": sections}
