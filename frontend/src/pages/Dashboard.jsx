import { Banknote, Coins, Landmark, Percent, PiggyBank, TrendingUp, Waves } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { compact, pct } from "@/lib/format";
import { Card, CardTitle, KpiCard, PageHeader, Spinner } from "@/components/common";
import { Donut, HBars, IncomeExpense, ProjectionChart, TrendChart } from "@/components/charts";
import InsightPanel from "@/components/InsightPanel";

export default function Dashboard() {
  const { t, lang, user } = useApp();
  const { data, loading } = useDashboard();
  const scope = useScopeLabel();
  if (loading || !data) return <Spinner />;
  const s = data.summary, cf = data.cashflow, b = data.breakdowns;
  const c = (v) => compact(v, lang);
  const kpis = [
    ["total_assets", s.total_assets, c, Landmark, "emerald"], ["total_liabilities", s.total_liabilities, c, Banknote, "navy"],
    ["net_worth", s.net_worth, c, PiggyBank, "gold"], ["annual_investment_income", s.annual_investment_income, c, TrendingUp, "emerald"],
    ["annual_dividends", s.dividends, c, Coins, "emerald"], ["annual_cashflow", cf.cf_y, c, Waves, cf.cf_y < 0 ? "red" : "emerald"],
    ["yield", s.total_return_pct, (v) => pct(v), Percent, "gold"],
  ];
  return (
    <div data-testid="dashboard-page">
      <PageHeader eyebrow={`${t("dashboard")} · ${scope}`} title={`${lang === "ja" ? "" : "Welcome, "}${user.name}${lang === "ja" ? " 様" : ""}`} sub={t("tagline")} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {kpis.map(([k, v, f, I, a], i) => <KpiCard key={k} label={t(k)} value={v} format={f} icon={I} accent={a} testid={`kpi-${k}`} delay={i * 60} />)}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2"><CardTitle>{t("asset_trend")}</CardTitle><TrendChart data={data.trend} keys={["total_assets", "net_worth", "total_liabilities"]} testid="chart-asset-trend" /></Card>
        <Card><CardTitle>{t("allocation")}</CardTitle><Donut data={b.asset_class} testid="chart-allocation" /></Card>
      </div>
      <div className="mt-6"><InsightPanel insights={data.insights} /></div>
      <div className="mt-6 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <Card><CardTitle>{t("by_country")}</CardTitle><Donut data={b.country} testid="chart-country" /></Card>
        <Card><CardTitle>{t("by_currency")}</CardTitle><Donut data={b.currency} testid="chart-currency" /></Card>
        <Card><CardTitle>{t("by_owner")}</CardTitle><Donut data={b.owner_type} testid="chart-owner" /></Card>
        <Card><CardTitle>{t("liability_mix")}</CardTitle><HBars data={b.liability_type} color="#0B3A5B" testid="chart-liabilities" /></Card>
        <Card><CardTitle>{t("income_expense")}</CardTitle><IncomeExpense cf={cf} /></Card>
        <Card><CardTitle right={<span className="text-[10px] font-semibold uppercase tracking-wider text-amber-600">{t("estimate")}</span>}>{t("future_projection")}</CardTitle><ProjectionChart rows={data.projection.rows} height={240} /></Card>
      </div>
    </div>
  );
}
