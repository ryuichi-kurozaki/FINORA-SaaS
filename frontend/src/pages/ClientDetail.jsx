import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Sparkles } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useState } from "react";
import { useApp } from "@/context/AppContext";
import { useDashboard } from "@/lib/useDashboard";
import { compact, pct, yen } from "@/lib/format";
import { Card, CardTitle, KpiCard, PageHeader, Spinner } from "@/components/common";
import { Donut, TrendChart } from "@/components/charts";
import EntityManager from "@/components/EntityManager";
import EContractPanel from "@/components/econtract/EContractPanel";
import TerminateDialog from "@/components/TerminateDialog";
import InsightPanel from "@/components/InsightPanel";
import AIAssistant from "@/components/AIAssistant";
import { DocumentsPanel } from "@/pages/Documents";
import { PositionsTable } from "@/pages/Transactions";
import { ConsultingPanels } from "@/pages/ConsultingHub";
import { TimelineList } from "@/pages/Timeline";
import GoalsPanel from "@/components/GoalsPanel";
import HealthPanel from "@/components/HealthPanel";
import SnapshotsPanel from "@/components/SnapshotsPanel";
import { InvoiceList, PaymentsList } from "@/pages/Billing";
import { InvitationsList } from "@/components/ClientOverviewTable";
import { useApi } from "@/lib/api";
import CorrectionDialog from "@/components/CorrectionDialog";

const PROFILE = ["client_type", "email", "phone", "address", "occupation", "business", "family", "related_corps", "annual_income", "income", "investment_experience", "investment_purpose", "risk_tolerance", "status", "notes"];
const SELECTS = ["client_type", "risk_tolerance", "status"];

export default function ClientDetail() {
  const { id } = useParams();
  const { t, lang, clients, isClient, setScopeClient, refreshClients } = useApp();
  const c = clients.find((x) => x.id === id);
  const { data, reload } = useDashboard(id);
  const [ai, setAi] = useState(false);
  const [corr, setCorr] = useState(false);
  const [term, setTerm] = useState(false);
  const { data: invs } = useApi(`/invoices?client_id=${id}`, [id]);
  if (!c || !data) return <Spinner />;
  const s = data.summary;
  const tabs = ["overview", "assets", "portfolio", "accounts", "transactions", "liabilities", "cashflows", "goals", "documents", "data_health", "ai_insight", "consulting", "timeline", "reports", "contracts", "billing", "tasks"];
  const unpaid = (invs || []).reduce((a, i) => a + (["ISSUED", "PARTIALLY_PAID", "OVERDUE"].includes(i.status) ? i.balance : 0), 0);
  return (
    <div data-testid="client-detail-page">
      <Link to="/clients" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-[#00A878]" data-testid="client-back-link"><ArrowLeft className="h-4 w-4" />{t("clients")}</Link>
      <PageHeader eyebrow={`${t(c.client_type)} · ${c.status ? t(c.status) : ""}`} title={c.corporate_name || c.name} sub={c.corporate_name ? c.name : c.occupation}>
        <button onClick={() => setAi(true)} className="btn-emerald inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold" data-testid="client-ask-ai-btn"><Sparkles className="h-4 w-4" />{t("ask_ai")}</button>
        {!isClient && (c.status === "terminated"
          ? <span className="rounded-xl bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-600" data-testid="client-terminated-badge">{t("term_client_badge")}{c.terminated_end_date ? ` · ${c.terminated_end_date}` : ""}</span>
          : <button onClick={() => setTerm(true)} className="inline-flex items-center rounded-xl border border-red-200 bg-white px-4 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50" data-testid="client-terminate-btn">{t("term_client")}</button>)}
      </PageHeader>
      {term && <TerminateDialog path={`/clients/${id}/terminate`} title={`${t("term_client")} — ${c.corporate_name || c.name}`} desc={t("term_client_desc")} onClose={() => setTerm(false)} onDone={() => { refreshClients(); reload(); }} testid="client-term" />}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard label={t("total_assets")} value={s.total_assets} format={(v) => compact(v, lang)} testid="client-kpi-assets" />
        <KpiCard label={t("total_liabilities")} value={s.total_liabilities} format={(v) => compact(v, lang)} accent="navy" testid="client-kpi-liabilities" />
        <KpiCard label={t("net_worth")} value={s.net_worth} format={(v) => compact(v, lang)} accent="gold" testid="client-kpi-networth" />
        <KpiCard label={t("yield")} value={s.total_return_pct} format={(v) => pct(v)} testid="client-kpi-yield" />
      </div>
      {unpaid > 0 && <div className="mt-4 inline-flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-700" data-testid="client-unpaid-badge">{t("unpaid_badge")} · <span className="font-num">{yen(unpaid)}</span></div>}
      <Tabs defaultValue="overview" className="mt-6">
        <TabsList className="h-auto flex-wrap justify-start bg-white/70 p-1">
          {tabs.map((k) => <TabsTrigger key={k} value={k} data-testid={`client-tab-${k}`} className="data-[state=active]:bg-[#071A2B] data-[state=active]:text-white">{t(k === "cashflows" ? "cashflow" : k === "overview" ? "overview" : k)}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="overview" className="mt-5 space-y-6">
          <div className="grid gap-6 xl:grid-cols-3">
            <Card>
              <CardTitle>{t("profile")}</CardTitle>
              <dl className="space-y-2.5 text-sm">
                {PROFILE.filter((k) => c[k]).map((k) => (
                  <div key={k} className="grid grid-cols-[120px_1fr] gap-2"><dt className="text-xs text-slate-500">{t(k === "income" ? "income_field" : k)}</dt>
                    <dd className="break-words text-slate-800">{SELECTS.includes(k) ? t(c[k]) : typeof c[k] === "number" ? yen(c[k]) : c[k]}</dd></div>
                ))}
              </dl>
              <p className="mt-4 rounded-lg bg-emerald-50/60 p-2.5 text-[11px] text-emerald-800">{t("derived_note")}</p>
            </Card>
            <Card className="xl:col-span-2"><CardTitle>{t("net_worth_trend")}</CardTitle><TrendChart data={data.trend} keys={["net_worth", "invested_value"]} testid="client-trend-chart" /></Card>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <Card><CardTitle>{t("allocation")}</CardTitle><Donut data={data.breakdowns.asset_class} /></Card>
            <Card><CardTitle>{t("by_institution")}</CardTitle><Donut data={data.breakdowns.institution} /></Card>
          </div>
          <InsightPanel insights={data.insights} />
        </TabsContent>
        {["accounts", "assets", "liabilities", "cashflows", "tasks"].map((e) => (
          <TabsContent key={e} value={e} className="mt-5"><EntityManager entity={e} clientId={id} title={t(e === "cashflows" ? "cashflow" : e)} onChange={reload} /></TabsContent>
        ))}
        <TabsContent value="transactions" className="mt-5 space-y-6"><PositionsTable clientId={id} /><EntityManager entity="transactions" clientId={id} title={t("transactions")} onChange={reload} /></TabsContent>
        <TabsContent value="portfolio" className="mt-5 space-y-6">
          <div className="grid gap-6 md:grid-cols-3">
            <Card><CardTitle>{t("by_currency")}</CardTitle><Donut data={data.breakdowns.currency} /></Card>
            <Card><CardTitle>{t("by_country")}</CardTitle><Donut data={data.breakdowns.country} /></Card>
            <Card><CardTitle>{t("by_sector")}</CardTitle><Donut data={data.breakdowns.sector} /></Card>
          </div>
          <SnapshotsPanel clientId={id} current={s} />
          {!isClient && <button onClick={() => setCorr(true)} className="rounded-xl border border-[#C9A227]/50 bg-[#C9A227]/10 px-4 py-2 text-sm font-semibold text-[#8a6d12]" data-testid="portfolio-correction-btn">{t("request_correction")}</button>}
        </TabsContent>
        <TabsContent value="goals" className="mt-5 space-y-6"><GoalsPanel goals={data.goals} /><EntityManager entity="goals" clientId={id} title={t("goals")} onChange={reload} /></TabsContent>
        <TabsContent value="data_health" className="mt-5"><HealthPanel health={data.health} clientId={id} /></TabsContent>
        <TabsContent value="ai_insight" className="mt-5 space-y-6"><InsightPanel insights={data.insights} /><Card className="h-[560px]"><AIAssistant clientId={id} /></Card></TabsContent>
        <TabsContent value="consulting" className="mt-5"><ConsultingPanels clientId={id} /></TabsContent>
        <TabsContent value="timeline" className="mt-5"><Card><TimelineList clientId={id} /></Card></TabsContent>
        <TabsContent value="reports" className="mt-5"><Card><Link to="/reports" onClick={() => setScopeClient(id)} className="btn-emerald inline-flex rounded-xl px-4 py-2.5 text-sm font-semibold" data-testid="client-reports-link">{t("reports")} →</Link></Card></TabsContent>
        <TabsContent value="documents" className="mt-5"><DocumentsPanel clientId={id} /></TabsContent>
        <TabsContent value="contracts" className="mt-5"><EContractPanel clientId={id} allowCreate /></TabsContent>
        <TabsContent value="billing" className="mt-5 space-y-6"><InvoiceList clientId={id} /><PaymentsList clientId={id} /><InvitationsList clientId={id} /></TabsContent>
      </Tabs>
      <CorrectionDialog open={corr} onOpenChange={setCorr} clientId={id} entity="portfolio" targetLabel={c.corporate_name || c.name} />
      <Sheet open={ai} onOpenChange={setAi}>
        <SheetContent side="right" className="flex w-full flex-col bg-[#F7F9FC] sm:max-w-xl" data-testid="client-ai-drawer">
          <SheetHeader><SheetTitle className="flex items-center gap-2 font-display"><Sparkles className="h-4 w-4 text-[#00A878]" />FINORA AI · {c.corporate_name || c.name}</SheetTitle></SheetHeader>
          <div className="mt-4 min-h-0 flex-1"><AIAssistant clientId={id} /></div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
