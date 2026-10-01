import BusinessOverview from "@/components/BusinessOverview";
import { Banknote, Coins, Landmark, Percent, PiggyBank, TrendingUp, Waves } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { compact, pct, yen } from "@/lib/format";
import { Card, CardTitle, KpiCard, PageHeader, Spinner } from "@/components/common";
import { Donut, HBars, IncomeExpense, ProjectionChart, TrendChart } from "@/components/charts";
import InsightPanel from "@/components/InsightPanel";
import NetWorthHistory from "@/components/NetWorthHistory";
import GoalsPanel from "@/components/GoalsPanel";
import HealthPanel from "@/components/HealthPanel";
import ActionCenter from "@/components/ActionCenter";

export default function Dashboard() {
  const { t, lang, user, isClient, scopeClient } = useApp();
  const { data, loading } = useDashboard();
  const scope = useScopeLabel();
  if (loading || !data) return <Spinner />;
  const s = data.summary, cf = data.cashflow, b = data.breakdowns;
  const c = (v) => yen(v);
  const kpis = [
    ["total_assets", s.total_assets, c, Landmark, "emerald"], ["total_liabilities", s.total_liabilities, c, Banknote, "navy"],
    ["net_worth", s.net_worth, c, PiggyBank, "gold"], ["investment_pl", s.unrealized_pl + s.realized_pl, c, TrendingUp, s.unrealized_pl + s.realized_pl < 0 ? "red" : "emerald"],
    ["annual_div_int", s.dividends + s.interest, c, Coins, "emerald"], ["annual_cashflow", cf.cf_y, c, Waves, cf.cf_y < 0 ? "red" : "emerald"],
    ["yield", s.total_return_pct, (v) => pct(v), Percent, "gold"],
  ];
  return (
    <div data-testid="dashboard-page">
      <PageHeader eyebrowCls="text-[22px]" eyebrow={user.role === "consultant" ? scope : `${t("dashboard")} · ${scope}`}
        title={user.role === "consultant" ? t("dashboard") : `${t("welcome_prefix")}${user.name}${t("welcome_suffix")}`} sub={t("tagline")} />
      {isClient && <div className="mb-6"><ActionCenter health={data.health} /></div>}
      {!isClient && !scopeClient && <BusinessOverview />}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        {kpis.map(([k, v, f, I, a], i) => <KpiCard key={k} label={t(k)} value={v} format={f} icon={I} accent={a} testid={`kpi-${k}`} delay={i * 60} />)}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <NetWorthHistory clientId={scopeClient} className="xl:col-span-2" />
        <Card><CardTitle>{t("allocation")}</CardTitle><Donut data={b.asset_class} testid="chart-allocation" /></Card>
      </div>
      <div className="mt-6"><InsightPanel insights={data.insights} /></div>
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <GoalsPanel goals={data.goals} />
        <HealthPanel health={data.health} compact clientId={scopeClient} />
      </div>
      <div className="mt-6 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <Card className="md:col-span-2 xl:col-span-3"><CardTitle>{t("asset_trend")}</CardTitle><TrendChart data={data.trend} keys={["total_assets", "net_worth", "total_liabilities"]} testid="chart-asset-trend" /></Card>
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
