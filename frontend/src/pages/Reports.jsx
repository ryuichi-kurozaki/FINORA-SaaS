import { useRef, useState } from "react";
import { FileDown } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { useDashboard } from "@/lib/useDashboard";
import { fmtDate, pct, plColor, yen } from "@/lib/format";
import { Card, PageHeader, Spinner } from "@/components/common";
import { Donut, TrendChart } from "@/components/charts";
import { LogoMark } from "@/components/Logo";
import { InsightItems } from "@/components/InsightPanel";
import { AnswerSections } from "@/components/AIAssistant";

const TYPES = ["rpt_total_assets", "rpt_liabilities", "rpt_net_worth", "rpt_portfolio", "rpt_pl", "rpt_income", "rpt_cashflow", "rpt_risk", "rpt_simulation", "rpt_ai", "rpt_consulting"];

function H({ children }) {
  return <h3 className="mb-3 mt-7 border-l-[3px] border-[#00A878] pl-3 font-display text-base font-bold text-[#071A2B]">{children}</h3>;
}

function T({ head, rows }) {
  return (
    <table className="w-full text-[12px]">
      <thead><tr className="bg-[#071A2B] text-white">{head.map((h, i) => <th key={i} className={`px-3 py-2 font-medium ${i ? "text-right" : "text-left"}`}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i} className={i % 2 ? "bg-[#F7F9FC]" : ""}>{r.map((c, j) => <td key={j} className={`px-3 py-1.5 ${j ? "text-right font-num" : ""}`}>{c}</td>)}</tr>)}</tbody>
    </table>
  );
}

function Body({ type, d, cid }) {
  const { t } = useApp();
  const q = cid ? `?client_id=${cid}` : "";
  const { data: assets } = useApi(`/data/assets${q}`, [cid]);
  const { data: liabs } = useApi(`/data/liabilities${q}`, [cid]);
  const { data: cons } = useApi(type === "rpt_consulting" ? `/data/consulting${q}` : null, [cid, type]);
  const { lang } = useApp();
  const { data: ai } = useApi(["rpt_ai", "rpt_consulting"].includes(type) ? `/ai/report?lang=${lang}${cid ? `&client_id=${cid}` : ""}` : null, [cid, type, lang]);
  const b = d.breakdowns, s = d.summary, cf = d.cashflow;
  const bd = (list) => <T head={[t("category"), t("amount"), "%"]} rows={list.map((x) => [t(x.key), yen(x.value), `${x.pct}%`])} />;
  switch (type) {
    case "rpt_total_assets": return <><H>{t("by_asset_class")}</H><div className="grid grid-cols-2 gap-6"><Donut data={b.asset_class} height={200} />{bd(b.asset_class)}</div><H>{t("by_country")}</H>{bd(b.country)}<H>{t("by_currency")}</H>{bd(b.currency)}</>;
    case "rpt_liabilities": return <><H>{t("liabilities")}</H><T head={[t("institution"), t("liability_type"), t("balance"), t("interest_rate"), t("monthly_payment"), t("maturity_date")]} rows={(liabs || []).map((l) => [`${l.institution} (${l.client_name})`, t(l.liability_type), yen(l.balance), `${l.interest_rate}% ${t(l.rate_type || "")}`, yen(l.monthly_payment), fmtDate(l.maturity_date)])} /><H>{t("liability_mix")}</H>{bd(b.liability_type)}</>;
    case "rpt_net_worth": return <><H>{t("net_worth_trend")}</H><TrendChart data={d.trend} keys={["net_worth", "total_assets", "total_liabilities"]} height={240} /><T head={[t("date"), t("total_assets"), t("total_liabilities"), t("net_worth")]} rows={d.trend.slice(-12).map((x) => [x.date, yen(x.total_assets), yen(x.total_liabilities), yen(x.net_worth)])} /></>;
    case "rpt_portfolio": return <><H>{t("by_asset_class")}</H>{bd(b.asset_class)}<H>{t("by_sector")}</H>{bd(b.sector)}<H>{t("by_institution")}</H>{bd(b.institution)}<H>{t("by_owner")}</H>{bd(b.owner_type)}</>;
    case "rpt_pl": return <><H>{t("holdings")}</H><T head={[t("asset_name"), t("acquisition_total"), t("value_jpy"), t("pl_jpy"), "%"]} rows={(assets || []).map((a) => [a.name, yen(a.cost_jpy), yen(a.value_jpy), <span className={plColor(a.pl_jpy)}>{yen(a.pl_jpy)}</span>, pct(a.unrealized_pct)])} /></>;
    case "rpt_income": return <><H>{t("rpt_income")}</H><T head={[t("asset_name"), t("dividend_annual"), t("interest_annual"), t("dividend_yield")]} rows={(assets || []).filter((a) => a.dividend_jpy || a.interest_jpy).map((a) => [a.name, yen(a.dividend_jpy), yen(a.interest_jpy), pct(((a.dividend_jpy + a.interest_jpy) / (a.value_jpy || 1)) * 100, false)])} /></>;
    case "rpt_cashflow": return <><H>{t("monthly_cf")}</H><T head={[t("category"), t("amount")]} rows={[[t("income"), yen(cf.income_m)], [t("expense"), yen(cf.expense_m)], [t("monthly_cf"), yen(cf.cf_m)], [t("annual_cashflow"), yen(cf.cf_y)], [t("free_cash"), yen(cf.free_m)], [`${t("investable")} (${t("estimate")})`, yen(cf.investable_m)]]} /><H>{t("income")}</H>{bd(cf.income_by.map((x) => ({ ...x, pct: ((x.value / (cf.income_m || 1)) * 100).toFixed(1) })))}<H>{t("expense")}</H>{bd(cf.expense_by.map((x) => ({ ...x, pct: ((x.value / (cf.expense_m || 1)) * 100).toFixed(1) })))}</>;
    case "rpt_risk": return <><H>{t("risk_score")}: {d.risk.score}/100</H><T head={[t("risk"), t("score"), t("threshold"), t("status")]} rows={d.risk.items.map((i) => [t({ currency: "currency_risk", country: "country_risk", sector: "sector_risk", interest_rate: "interest_rate_risk", balance: "balance_risk" }[i.code] || i.code), i.value, `${i.reverse ? "<" : ">"} ${i.warn}`, t(i.level)])} /><H>{t("risks_to_watch")}</H><InsightItems items={d.insights.risks} /></>;
    case "rpt_simulation": return <><H>{t("scenario_compare")}</H><T head={[t("years"), t("bull"), t("base"), t("bear"), t("debt")]} rows={d.projection.rows.filter((r) => r.year % 5 === 0).map((r) => [r.year, yen(r.bull), yen(r.base), yen(r.bear), yen(r.debt)])} /><p className="mt-3 text-[11px] text-slate-500">{t("estimate")}: {t("bull")} 8% / {t("base")} 5% / {t("bear")} 1%</p></>;
    case "rpt_ai": return <><H>{t("ai_title")}</H>{["summary", "changes", "risks", "checks", "missing"].map((k) => <div key={k} className="mb-4"><div className="mb-1 text-xs font-bold text-slate-500">{t({ summary: "ai_summary", changes: "important_changes", risks: "risks_to_watch", checks: "items_to_check", missing: "missing_data" }[k])}</div><InsightItems items={d.insights[k]} /></div>)}</>;
    case "rpt_consulting": return <><H>{t("consulting_history")}</H><T head={[t("date"), t("kind"), t("title"), t("next_action")]} rows={(cons || []).map((c) => [fmtDate(c.date), t(c.kind), c.title, c.next_action || "—"])} />{ai && <><H>{t("ai_summary")}</H><AnswerSections sections={ai.sections} /></>}</>;
    default: return null;
  }
}

export default function Reports() {
  const { t, lang, user, clients, scopeClient, clientName } = useApp();
  const [type, setType] = useState(TYPES[0]);
  const [cid, setCid] = useState(scopeClient);
  const { data } = useDashboard(cid);
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);

  const exportPdf = async () => {
    setBusy(true);
    try {
      const html2pdf = (await import("html2pdf.js")).default;
      await html2pdf().set({ margin: [8, 8, 10, 8], filename: `FINORA_${type}_${new Date().toISOString().slice(0, 10)}.pdf`, image: { type: "jpeg", quality: 0.96 }, html2canvas: { scale: 2, useCORS: true }, jsPDF: { unit: "mm", format: "a4" }, pagebreak: { mode: ["css", "legacy"] } }).from(ref.current).save();
    } catch (e) { toast.error(String(e)); } finally { setBusy(false); }
  };

  const s = data?.summary;
  return (
    <div data-testid="reports-page">
      <PageHeader eyebrow="Reports" title={t("reports")}>
        {user.role !== "client" && (
          <select value={cid} onChange={(e) => setCid(e.target.value)} className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm" data-testid="report-client-select">
            <option value="">{t("all_clients")}</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.corporate_name || c.name}</option>)}
          </select>
        )}
        <Button className="btn-emerald" onClick={exportPdf} disabled={busy || !data} data-testid="report-pdf-export-button"><FileDown className="mr-1 h-4 w-4" />{busy ? t("loading") : t("export_pdf")}</Button>
      </PageHeader>
      <div className="grid gap-6 xl:grid-cols-[260px_1fr]">
        <Card className="h-fit p-3">
          {TYPES.map((k) => (
            <button key={k} onClick={() => setType(k)} data-testid={`report-type-${k}`}
              className={`block w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${type === k ? "bg-[#071A2B] text-white" : "text-slate-600 hover:bg-slate-100"}`}>{t(k)}</button>
          ))}
        </Card>
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-slate-100 p-4 sm:p-8">
          {!data ? <Spinner /> : (
            <div ref={ref} className="report-doc mx-auto w-[794px] max-w-none p-10 shadow-xl" data-testid="report-document">
              <div className="flex items-center justify-between border-b-2 border-[#071A2B] pb-4">
                <div className="flex items-center gap-3"><LogoMark size={36} /><div><div className="font-display text-xl font-extrabold tracking-[0.14em]"><span className="text-[#071A2B]">FIN</span><span className="text-[#00A878]">ORA</span></div><div className="text-[9px] uppercase tracking-[0.25em] text-slate-500">Investment Intelligence</div></div></div>
                <div className="text-right text-[11px] text-slate-500"><div className="font-semibold text-[#C9A227]">{t("confidential")}</div><div>{t("generated")}: {new Date().toISOString().slice(0, 10)}</div><div>{t("prepared_by")}: {user.name}</div></div>
              </div>
              <h2 className="mt-6 font-display text-2xl font-extrabold text-[#071A2B]" data-testid="report-title">{t(type)}</h2>
              <div className="mt-1 text-sm text-slate-500">{t("target")}: {cid ? clientName(cid) : t("all_clients")}</div>
              <div className="mt-5 grid grid-cols-4 gap-3">
                {[["total_assets", s.total_assets], ["total_liabilities", s.total_liabilities], ["net_worth", s.net_worth], ["yield", null]].map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-slate-200 p-3"><div className="text-[10px] uppercase tracking-wider text-slate-500">{t(k)}</div><div className={`mt-1 font-num text-sm font-semibold ${k === "net_worth" ? "text-[#C9A227]" : "text-[#071A2B]"}`}>{v == null ? pct(s.total_return_pct) : yen(v)}</div></div>
                ))}
              </div>
              <Body key={`${type}-${cid}-${lang}`} type={type} d={data} cid={cid} />
              <div className="mt-10 border-t border-slate-200 pt-3 text-[10px] text-slate-400">FINORA · www.finora.co.jp — {t("ai_engine_note")}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
