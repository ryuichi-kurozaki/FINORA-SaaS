import { useMemo, useState } from "react";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { compact, num, pct, plColor, yen } from "@/lib/format";
import { Card, CardTitle, KpiCard, PageHeader, Spinner } from "@/components/common";
import { Donut, HBars } from "@/components/charts";
import EntityManager from "@/components/EntityManager";
import PriceSync from "@/components/PriceSync";
import TxHistoryDialog from "@/components/TxHistoryDialog";

const INVEST = new Set(["jp_stock", "foreign_stock", "etf", "fund", "bond", "fx", "crypto", "gold", "precious_metal", "unlisted", "real_estate"]);

function bd(list, keyFn, val = "value_jpy") {
  const agg = {};
  list.forEach((a) => { const k = keyFn(a) || "other"; agg[k] = (agg[k] || 0) + (a[val] || 0); });
  const tot = Object.values(agg).reduce((x, v) => x + v, 0) || 1;
  return Object.entries(agg).filter(([, v]) => v).map(([k, v]) => ({ key: k, value: Math.round(v), pct: Math.round((v / tot) * 1000) / 10 })).sort((a, b2) => b2.value - a.value);
}

function acctSummary(list) {
  const sum = (f) => list.reduce((x, a) => x + (a[f] || 0), 0);
  const inv = list.filter((a) => INVEST.has(a.asset_class));
  const ta = sum("value_jpy");
  const principal = inv.reduce((x, a) => x + (a.cost_jpy || 0), 0);
  const invested = inv.reduce((x, a) => x + (a.value_jpy || 0), 0);
  return { total_assets: ta, total_liabilities: 0, net_worth: ta, principal, invested_value: invested, unrealized_pl: invested - principal, realized_pl: sum("realized_jpy"), dividends: sum("dividend_jpy"), interest: sum("interest_jpy") };
}

function acctBreakdowns(list, instMap) {
  const inv = list.filter((a) => INVEST.has(a.asset_class));
  return {
    asset_class: bd(list, (a) => a.asset_class),
    country: bd(list, (a) => a.country || "JP"),
    currency: bd(list, (a) => a.currency || "JPY"),
    sector: bd(inv, (a) => a.sector),
    institution: bd(list, (a) => instMap[a.account_id] || "unassigned"),
    owner_type: bd(list, (a) => a.owner_type || "individual"),
  };
}

export default function Portfolio() {
  const { t, lang, scopeClient, isClient, user } = useApp();
  const { data, reload } = useDashboard();
  const { data: assets, reload: reloadAssets } = useApi(`/data/assets${scopeClient ? `?client_id=${scopeClient}` : ""}`, [scopeClient]);
  const { data: accounts, reload: reloadAccounts } = useApi(`/data/accounts${scopeClient ? `?client_id=${scopeClient}` : ""}`, [scopeClient]);
  const { data: pos } = useApi(`/positions${scopeClient ? `?client_id=${scopeClient}` : ""}`, [scopeClient]);
  const { data: txData } = useApi(`/data/transactions${scopeClient ? `?client_id=${scopeClient}` : ""}`, [scopeClient]);
  const posMap = useMemo(() => Object.fromEntries((pos || []).map((p) => [p.asset_id, p])), [pos]);
  const [acct, setAcct] = useState("");
  const [sel, setSel] = useState(null);
  const scope = useScopeLabel();
  const allAssets = assets || [];
  const instMap = useMemo(() => Object.fromEntries((accounts || []).map((a) => [a.id, a.institution])), [accounts]);
  const hasOrphan = allAssets.some((a) => !a.account_id);
  const filtered = useMemo(() => (acct ? allAssets.filter((a) => (acct === "none" ? !a.account_id : a.account_id === acct)) : allAssets), [acct, assets]);
  const view = useMemo(() => (acct ? { s: acctSummary(filtered), b: acctBreakdowns(filtered, instMap) } : null), [acct, filtered, instMap]);
  if (!data) return <Spinner />;
  const s = acct ? view.s : data.summary;
  const b = acct ? view.b : data.breakdowns;
  const holdings = acct ? filtered : allAssets;
  const c = (v) => yen(v);
  const k = [["total_assets", s.total_assets], ["total_liabilities", s.total_liabilities], ["net_worth", s.net_worth], ["principal", s.principal],
    ["invested_value", s.invested_value], ["unrealized_pl", s.unrealized_pl], ["realized_pl", s.realized_pl], ["dividends", s.dividends], ["interest", s.interest]];
  return (
    <div data-testid="portfolio-page">
      <div className="mb-4"><PriceSync clientId={isClient ? user.client_id : scopeClient} onChange={() => { reload(); reloadAssets(); }} /></div>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <PageHeader eyebrow={`Portfolio · ${scope}`} title={t("portfolio")} />
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500">{t("account_id")}</span>
          <select value={acct} onChange={(e) => setAcct(e.target.value)} data-testid="portfolio-account-select"
            className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40">
            <option value="">{t("all_accounts")}</option>
            {(accounts || []).map((a) => <option key={a.id} value={a.id}>{a.institution}{a.currency ? ` (${a.currency})` : ""}</option>)}
            {hasOrphan && <option value="none">{t("account_unassigned")}</option>}
          </select>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
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
        <CardTitle right={<span className="text-[11px] font-normal text-slate-400">{t("view_tx_hint")}</span>}>{t("holdings")}</CardTitle>
        <div className="-mx-2 overflow-x-auto">
          <table className="data-table w-full min-w-[900px] text-sm" data-testid="holdings-table">
            <thead><tr>{["asset_name", "asset_class", "client", "currency", "quantity", "acquisition_total", "current_value", "value_jpy", "pl_jpy", "tx_count", "realized_pl", "dividends", "dividend_yield"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
            <tbody>
              {holdings.sort((a, b2) => b2.value_jpy - a.value_jpy).map((a) => {
                const p = posMap[a.id];
                return (
                <tr key={a.id} onClick={() => setSel(a)} className="cursor-pointer transition-colors hover:bg-emerald-50/60">
                  <td className="font-medium text-[#0B6E4F] hover:underline">{a.name}{a.ticker && <span className="ml-1.5 font-num text-xs text-slate-400">{a.ticker}</span>}
                    {p?.qty_mismatch && <span className="ml-1.5 text-xs text-amber-600" title={`${t("qty_from_tx")}: ${num(p.qty, 4)}`} data-testid={`qty-mismatch-${a.id}`}>⚠</span>}</td>
                  <td>{t(a.asset_class)}</td><td className="text-slate-600">{a.client_name}</td><td className="font-num">{a.currency}</td>
                  <td className="font-num">{num(a.quantity, 4)}</td><td className="font-num">{num(a.acquisition_total)}</td><td className="font-num">{num(a.current_value)}</td>
                  <td className="font-num font-medium">{yen(a.value_jpy)}</td>
                  <td className={`font-num ${plColor(a.pl_jpy)}`}>{yen(a.pl_jpy)} <span className="text-xs">({pct(a.unrealized_pct)})</span></td>
                  <td className="font-num text-slate-600">{p ? num(p.tx_count) : "—"}</td>
                  <td className={`font-num ${plColor(p?.realized || 0)}`}>{p ? yen(p.realized) : "—"}</td>
                  <td className="font-num text-slate-600">{p ? yen(p.dividends + p.interest) : "—"}</td>
                  <td className="font-num">{a.value_jpy ? pct(((a.dividend_jpy + a.interest_jpy) / a.value_jpy) * 100, false) : "—"}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      {isClient && user.client_id && <div className="mt-6" data-testid="portfolio-holdings-entry">
        <EntityManager entity="assets" clientId={user.client_id} title={t("my_holdings_entry")} onChange={() => { reload(); reloadAssets(); reloadAccounts(); }} /></div>}
      <TxHistoryDialog assetId={sel?.id} assetName={sel?.name} txs={txData} onClose={() => setSel(null)} />
    </div>
  );
}
