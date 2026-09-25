import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { compact, num, pct, plColor, yen } from "@/lib/format";
import { Card, CardTitle, KpiCard, PageHeader, Spinner } from "@/components/common";
import { Donut, HBars } from "@/components/charts";

export default function Portfolio() {
  const { t, lang, scopeClient } = useApp();
  const { data } = useDashboard();
  const { data: assets } = useApi(`/data/assets${scopeClient ? `?client_id=${scopeClient}` : ""}`, [scopeClient]);
  const scope = useScopeLabel();
  if (!data) return <Spinner />;
  const s = data.summary, b = data.breakdowns, c = (v) => compact(v, lang);
  const k = [["total_assets", s.total_assets], ["total_liabilities", s.total_liabilities], ["net_worth", s.net_worth], ["principal", s.principal],
    ["invested_value", s.invested_value], ["unrealized_pl", s.unrealized_pl], ["realized_pl", s.realized_pl], ["dividends", s.dividends], ["interest", s.interest]];
  return (
    <div data-testid="portfolio-page">
      <PageHeader eyebrow={`Portfolio · ${scope}`} title={t("portfolio")} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-9">
        {k.map(([key, v], i) => <KpiCard key={key} label={t(key)} value={v} format={c} accent={key === "net_worth" ? "gold" : key === "total_liabilities" ? "navy" : v < 0 ? "red" : "emerald"} testid={`pf-${key}`} delay={i * 40} />)}
      </div>
      <div className="mt-6 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <Card><CardTitle>{t("by_asset_class")}</CardTitle><Donut data={b.asset_class} /></Card>
        <Card><CardTitle>{t("by_country")}</CardTitle><Donut data={b.country} /></Card>
        <Card><CardTitle>{t("by_currency")}</CardTitle><Donut data={b.currency} /></Card>
        <Card><CardTitle>{t("by_sector")}</CardTitle><HBars data={b.sector} /></Card>
        <Card><CardTitle>{t("by_institution")}</CardTitle><HBars data={b.institution} color="#0B3A5B" /></Card>
        <Card><CardTitle>{t("by_owner")}</CardTitle><Donut data={b.owner_type} /></Card>
      </div>
      <Card className="mt-6">
        <CardTitle>{t("holdings")}</CardTitle>
        <div className="-mx-2 overflow-x-auto">
          <table className="data-table w-full min-w-[900px] text-sm" data-testid="holdings-table">
            <thead><tr>{["asset_name", "asset_class", "client", "currency", "quantity", "acquisition_total", "current_value", "value_jpy", "pl_jpy", "dividend_yield"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
            <tbody>
              {(assets || []).sort((a, b2) => b2.value_jpy - a.value_jpy).map((a) => (
                <tr key={a.id}>
                  <td className="font-medium">{a.name}{a.ticker && <span className="ml-1.5 font-num text-xs text-slate-400">{a.ticker}</span>}</td>
                  <td>{t(a.asset_class)}</td><td className="text-slate-600">{a.client_name}</td><td className="font-num">{a.currency}</td>
                  <td className="font-num">{num(a.quantity, 4)}</td><td className="font-num">{num(a.acquisition_total)}</td><td className="font-num">{num(a.current_value)}</td>
                  <td className="font-num font-medium">{yen(a.value_jpy)}</td>
                  <td className={`font-num ${plColor(a.pl_jpy)}`}>{yen(a.pl_jpy)} <span className="text-xs">({pct(a.unrealized_pct)})</span></td>
                  <td className="font-num">{a.value_jpy ? pct(((a.dividend_jpy + a.interest_jpy) / a.value_jpy) * 100, false) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
