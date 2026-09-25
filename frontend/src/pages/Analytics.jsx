import { Activity, ArrowDownRight, Gauge, Percent, Target, TrendingUp } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { compact, pct } from "@/lib/format";
import { Card, CardTitle, KpiCard, PageHeader, Spinner } from "@/components/common";
import { LinesChart, TrendChart } from "@/components/charts";

export default function Analytics() {
  const { t, lang } = useApp();
  const { data } = useDashboard();
  const scope = useScopeLabel();
  if (!data) return <Spinner />;
  const m = data.metrics, s = data.summary, c = (v) => compact(v, lang);
  const cards = [
    ["unrealized_pl", s.unrealized_pl, c, TrendingUp], ["realized_pl", s.realized_pl, c, TrendingUp], ["dividends", s.dividends, c, Percent], ["interest", s.interest, c, Percent],
    ["yield", s.total_return_pct, (v) => pct(v), Target], ["dividend_yield", s.dividend_yield_pct, (v) => pct(v, false), Percent],
    ["annual_return", m.annual_return_pct, (v) => pct(v), Activity], ["volatility", m.volatility_pct, (v) => pct(v, false), Gauge],
    ["max_drawdown", m.max_drawdown_pct, (v) => pct(v), ArrowDownRight], ["benchmark", m.benchmark_return_pct, (v) => pct(v), Target],
    ["excess_return", m.excess_return_pct, (v) => pct(v), TrendingUp], ["sharpe", m.sharpe, (v) => (v == null ? "—" : v.toFixed(2)), Gauge],
  ];
  return (
    <div data-testid="analytics-page">
      <PageHeader eyebrow={`Analytics · ${scope}`} title={t("analytics")} sub={`${t("estimate")}: ${m.months} ${t("months_short")} (snapshots)`} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        {cards.map(([k, v, f, I], i) => <KpiCard key={k} label={t(k)} value={v ?? 0} format={f} icon={I} accent={k === "max_drawdown" || (v ?? 0) < 0 ? "red" : i % 3 === 2 ? "gold" : "emerald"} testid={`an-${k}`} delay={i * 40} />)}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card><CardTitle>{t("benchmark_compare")}</CardTitle>
          <LinesChart data={data.trend} testid="chart-benchmark" lines={[
            { key: "invested_value", name: t("invested_value"), color: "#00A878", width: 2.6 },
            { key: "benchmark_value", name: t("benchmark"), color: "#C9A227", dash: "5 4" },
            { key: "principal", name: t("principal"), color: "#A0AEC0", dash: "3 3", width: 1.4 },
          ]} />
        </Card>
        <Card><CardTitle>{t("asset_trend")}</CardTitle><TrendChart data={data.trend} keys={["total_assets", "net_worth"]} /></Card>
      </div>
    </div>
  );
}
