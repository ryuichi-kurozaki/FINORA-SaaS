import { useApp } from "@/context/AppContext";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { compact, pct } from "@/lib/format";
import { Card, CardTitle, KpiCard, PageHeader } from "@/components/common";
import { HBars, IncomeExpense } from "@/components/charts";
import EntityManager from "@/components/EntityManager";

function CashflowSummary() {
  const { t, lang } = useApp();
  const { data } = useDashboard();
  if (!data) return null;
  const cf = data.cashflow, c = (v) => compact(v, lang);
  return (
    <>
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        <KpiCard label={t("income")} value={cf.income_m} format={c} sub={t("per_month")} testid="cf-income" />
        <KpiCard label={t("expense")} value={cf.expense_m} format={c} accent="navy" sub={t("per_month")} testid="cf-expense" />
        <KpiCard label={t("monthly_cf")} value={cf.cf_m} format={c} accent={cf.cf_m < 0 ? "red" : "emerald"} testid="cf-monthly" />
        <KpiCard label={t("annual_cashflow")} value={cf.cf_y} format={c} accent="gold" testid="cf-annual" />
        <KpiCard label={t("investable")} value={cf.investable_m} format={c} sub={`${t("free_cash")}: ${c(cf.free_m)}`} testid="cf-investable" />
      </div>
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Card><CardTitle>{t("income_expense")}</CardTitle><IncomeExpense cf={cf} /></Card>
        <Card><CardTitle>{t("income")}</CardTitle><HBars data={cf.income_by} /></Card>
        <Card><CardTitle>{t("expense")}</CardTitle><HBars data={cf.expense_by} color="#0B3A5B" /></Card>
      </div>
    </>
  );
}

function LiabilitySummary() {
  const { t, lang } = useApp();
  const { data } = useDashboard();
  if (!data) return null;
  const s = data.summary, c = (v) => compact(v, lang);
  const lev = data.risk.items.find((i) => i.code === "leverage");
  return (
    <div className="mb-6 grid gap-6 lg:grid-cols-3">
      <div className="grid grid-cols-2 gap-3 lg:col-span-1 lg:grid-cols-1">
        <KpiCard label={t("total_liabilities")} value={s.total_liabilities} format={c} accent="navy" testid="liab-total" />
        <KpiCard label={t("leverage")} value={lev?.value} format={(v) => pct(v, false)} accent={lev?.level === "ok" ? "emerald" : "red"} testid="liab-leverage" />
      </div>
      <Card className="lg:col-span-2"><CardTitle>{t("liability_mix")}</CardTitle><HBars data={data.breakdowns.liability_type} color="#0B3A5B" height={200} /></Card>
    </div>
  );
}

const META = {
  assets: { eyebrow: "Assets", summary: null }, accounts: { eyebrow: "Accounts" }, liabilities: { eyebrow: "Liabilities", summary: LiabilitySummary },
  cashflows: { eyebrow: "Cash Flow", summary: CashflowSummary, title: "cashflow" }, consulting: { eyebrow: "Consulting" }, tasks: { eyebrow: "Tasks" },
};

export default function EntityPage({ entity }) {
  const { t } = useApp();
  const scope = useScopeLabel();
  const m = META[entity];
  const Summary = m.summary;
  return (
    <div data-testid={`${entity}-page`}>
      <PageHeader eyebrow={`${m.eyebrow} · ${scope}`} title={t(m.title || entity)} />
      {Summary && <Summary />}
      <EntityManager key={entity} entity={entity} />
    </div>
  );
}
