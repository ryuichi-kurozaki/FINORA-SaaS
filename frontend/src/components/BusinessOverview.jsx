import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { compact, yen } from "@/lib/format";
import { Card, CardTitle, Spinner } from "@/components/common";

function Tile({ label, value, tone, testid }) {
  return (
    <div className="glass-card rounded-2xl p-4" data-testid={testid}>
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1 font-num text-xl font-semibold ${tone || "text-[#071A2B]"}`}>{value}</div>
    </div>
  );
}

function MonthlyChart({ data }) {
  const { t, lang } = useApp();
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => compact(v, lang)} tick={{ fontSize: 11 }} width={60} />
        <Tooltip formatter={(v) => yen(v)} /><Legend />
        <Bar dataKey="billed" name={t("billed")} fill="#071A2B" radius={[4, 4, 0, 0]} />
        <Bar dataKey="paid" name={t("received")} fill="#00A878" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function Ranking({ title, rows }) {
  const { t } = useApp();
  return (
    <Card><CardTitle>{title}</CardTitle>
      {!rows?.length ? <div className="py-6 text-center text-sm text-slate-400">{t("no_data")}</div> : rows.slice(0, 8).map((r) => (
        <div key={r.key} className="flex justify-between border-b border-slate-100 py-2 text-sm last:border-0"><span>{r.key}</span><span className="font-num font-semibold">{yen(r.value)}</span></div>
      ))}
    </Card>
  );
}

export function RevenueTiles({ s }) {
  const { t, lang } = useApp();
  const c = (v) => yen(v);
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <Tile label={t("billed_month")} value={c(s.billed_month)} testid="rev-billed-month" />
      <Tile label={t("paid_month")} value={c(s.paid_month)} tone="text-[#00A878]" testid="rev-paid-month" />
      <Tile label={t("billed_year")} value={c(s.billed_year)} testid="rev-billed-year" />
      <Tile label={t("paid_year")} value={c(s.paid_year)} tone="text-[#00A878]" testid="rev-paid-year" />
      <Tile label={`${t("outstanding")} (${s.outstanding_count})`} value={c(s.outstanding)} tone="text-[#C9A227]" testid="rev-outstanding" />
      <Tile label={`${t("overdue_amt")} (${s.overdue_count})`} value={c(s.overdue)} tone={s.overdue ? "text-red-600" : undefined} testid="rev-overdue" />
    </div>
  );
}

export function RevenuePanel() {
  const { t } = useApp();
  const { data: s } = useApi("/billing/summary");
  if (!s) return <Spinner />;
  return (
    <div className="space-y-6" data-testid="revenue-panel">
      <RevenueTiles s={s} />
      <Card><CardTitle>{t("monthly_rev")}</CardTitle><MonthlyChart data={s.monthly} /></Card>
      <div className="grid gap-6 md:grid-cols-2"><Ranking title={t("by_client_rev")} rows={s.by_client} /><Ranking title={t("by_contract_rev")} rows={s.by_contract} /></div>
    </div>
  );
}

export default function BusinessOverview() {
  const { t } = useApp();
  const { data } = useApi("/consultant/overview");
  if (!data) return <Spinner />;
  const u = t("count_unit");
  const tiles = [["clients_count", data.clients], ["new_clients", data.new_clients], ["active_contracts", data.active_contract_clients], ["meetings_month", data.meetings_month],
    ["open_requests", data.open_requests], ["waiting", data.waiting], ["reports_month", data.reports_month]];
  const links = [["clients", "/clients"], ["contracts", "/billing"], ["invoices", "/billing"], ["payments", "/billing"], ["consulting", "/consulting"], ["tasks", "/tasks"]];
  return (
    <section className="mb-6 space-y-4" data-testid="business-overview">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-bold text-[#071A2B]">{t("business_overview")}</h2>
        <div className="flex flex-wrap gap-2">{links.map(([k, to]) => <Link key={k} to={to} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:border-[#00A878] hover:text-[#00A878]" data-testid={`bo-link-${k}`}>{t(k)} →</Link>)}</div>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">{tiles.map(([k, v]) => <Tile key={k} label={t(k)} value={`${v}${u}`} testid={`bo-${k}`} />)}</div>
      <RevenueTiles s={data.billing} />
      <Card><CardTitle>{t("monthly_rev")}</CardTitle><MonthlyChart data={data.billing.monthly} /></Card>
    </section>
  );
}
