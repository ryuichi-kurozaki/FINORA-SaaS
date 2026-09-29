import { useState } from "react";
import { toast } from "sonner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import EContractPanel from "@/components/econtract/EContractPanel";
import PayoutsPanel from "@/components/PayoutsPanel";
import SiteAdmin from "@/components/SiteAdmin";
import EmailLogPanel from "@/components/EmailLogPanel";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate, fmtDateTime, yen } from "@/lib/format";
import { Card, CardTitle, PageHeader, Spinner } from "@/components/common";

const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm";

function EditTenant({ row, plans, onClose, onDone }) {
  const { t } = useApp();
  const [f, setF] = useState({ status: row?.status, plan_code: row?.plan_code, payment_status: row?.payment_status || "", renewal_date: row?.renewal_date || "", amount: row?.amount ?? "", billing_period: row?.billing_period || "monthly", fixed_fee: row?.fixed_fee ?? "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (clearFixed = false) => {
    try {
      await api.put(`/platform/tenants/${row.id}`, {
        ...f, amount: f.amount === "" ? null : Number(f.amount),
        fixed_fee: clearFixed || f.fixed_fee === "" ? null : Number(f.fixed_fee),
        clear_fixed_fee: clearFixed || undefined,
      });
      toast.success(t("saved")); onDone(); onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={!!row} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>{row?.name}</DialogTitle></DialogHeader>
        <div className="grid gap-3 text-xs text-slate-600">
          <label>{t("status")}<select className={inp} value={f.status} onChange={set("status")} data-testid="tenant-status">{["TRIAL", "ACTIVE", "SUSPENDED", "CANCELLED"].map((s) => <option key={s} value={s}>{t(s)}</option>)}</select></label>
          <label>{t("plan")}<select className={inp} value={f.plan_code} onChange={set("plan_code")} data-testid="tenant-plan">{plans.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select></label>
          <label>{t("payment_status")}<select className={inp} value={f.payment_status} onChange={set("payment_status")} data-testid="tenant-payment">{["none", "paid", "unpaid", "overdue"].map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
          <label>{t("renewal_date")}<input type="date" className={inp} value={f.renewal_date} onChange={set("renewal_date")} /></label>
          <div className="grid grid-cols-2 gap-3">
            <label>{t("amount")}<input type="number" className={inp} value={f.amount} onChange={set("amount")} data-testid="tenant-amount" /></label>
            <label>{t("billing_cycle")}<select className={inp} value={f.billing_period} onChange={set("billing_period")}><option value="monthly">{t("MONTHLY")}</option><option value="yearly">{t("YEARLY")}</option></select></label>
          </div>
        </div>
        <label className="text-xs text-slate-600">{t("fixed_fee")}
          <input type="number" className={inp} value={f.fixed_fee} onChange={set("fixed_fee")} placeholder={t("none_set")} data-testid="tenant-fixed-fee" />
          <span className="mt-1 block text-[11px] leading-relaxed text-slate-400">{t("fixed_fee_note")}</span>
        </label>
        <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-between">
          {row?.fixed_fee != null
            ? <Button variant="outline" onClick={() => save(true)} data-testid="tenant-fixed-fee-clear">{t("fixed_fee_clear")}</Button>
            : <span />}
          <Button className="btn-emerald" onClick={() => save(false)} data-testid="tenant-save">{t("save")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Tenants() {
  const { t } = useApp();
  const { data, reload } = useApi("/platform/tenants");
  const { data: plans } = useApi("/platform/plans");
  const [edit, setEdit] = useState(null);
  if (!data) return <Spinner />;
  const cnt = (s) => data.filter((x) => x.status === s).length;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[["tenants", data.length], ["ACTIVE", cnt("ACTIVE")], ["TRIAL", cnt("TRIAL")], ["SUSPENDED", cnt("SUSPENDED")], ["customers", data.reduce((a, x) => a + x.customers, 0)]].map(([k, v]) => (
          <div key={k} className="glass-card rounded-2xl p-4" data-testid={`platform-kpi-${k}`}><div className="text-[11px] uppercase tracking-wider text-slate-500">{t(k)}</div><div className="mt-1 font-num text-2xl font-semibold text-[#071A2B]">{v}</div></div>
        ))}
      </div>
      <Card>
        <CardTitle>{t("tenants")}</CardTitle>
        <div className="overflow-x-auto"><table className="data-table w-full min-w-[1000px] text-sm" data-testid="platform-tenant-table">
          <thead><tr>{["name", "owner", "status", "plan", "payment_status", "amount", "renewal_date", "members", "customers", "last_activity", ""].map((h) => <th key={h}>{h && t(h)}</th>)}</tr></thead>
          <tbody>{data.map((r) => (
            <tr key={r.id} data-testid={`platform-tenant-${r.id}`}>
              <td className="font-medium">{r.name}</td><td className="text-xs">{r.owner_name}<div className="text-slate-400">{r.owner_email}</div>{r.owner_whatsapp && <div className="text-slate-400" data-testid={`tenant-wa-${r.id}`}>WhatsApp: +{r.owner_whatsapp}</div>}{r.owner_line && <div className="text-slate-400" data-testid={`tenant-line-${r.id}`}>LINE: {r.owner_line}</div>}</td>
              <td><span className={`rounded-md px-2 py-0.5 text-xs ${r.status === "SUSPENDED" || r.status === "CANCELLED" ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>{t(r.status)}</span></td>
              <td>{r.plan_code || "—"}</td><td className="text-xs">{r.payment_status || "—"}</td><td className="font-num" data-testid={`tenant-fee-${r.id}`}>{yen(r.amount || 0)}{r.fixed_fee != null && <span className="ml-1 rounded-md bg-amber-50 px-1.5 py-0.5 font-sans text-[10px] font-semibold text-amber-700" data-testid={`tenant-fixed-badge-${r.id}`}>{t("fixed_fee_badge")}</span>}<div className="text-[10px] text-slate-400">{t("peak_customers")} {r.peak_customers ?? 0}</div></td>
              <td className="font-num text-xs">{r.renewal_date || "—"}</td><td className="text-center">{r.members}</td><td className="text-center">{r.customers}</td>
              <td className="font-num text-xs">{fmtDate(r.last_activity)}</td>
              <td><Button size="sm" variant="outline" onClick={() => setEdit(r)} data-testid={`platform-edit-${r.id}`}>{t("edit")}</Button></td>
            </tr>
          ))}</tbody>
        </table></div>
      </Card>
      {edit && <EditTenant row={edit} plans={plans || []} onClose={() => setEdit(null)} onDone={reload} />}
    </div>
  );
}

function Plans() {
  const { t } = useApp();
  const { data, reload } = useApi("/platform/plans");
  const save = async (p, k, v) => { try { await api.put(`/platform/plans/${p.code}`, { [k]: v === "" ? null : Number(v) }); toast.success(t("saved")); reload(); } catch (e) { toast.error(errMsg(e)); } };
  if (!data) return <Spinner />;
  return (
    <Card><CardTitle>{t("plans")}</CardTitle>
      <table className="data-table w-full text-sm" data-testid="platform-plan-table">
        <thead><tr>{["plan", "base_fee", "per_customer_fee", "price_monthly", "price_yearly"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
        <tbody>{data.map((p) => (
          <tr key={p.code}><td className="font-medium">{p.name} <span className="text-xs text-slate-400">{p.code}</span></td>
            {["base_fee", "per_customer_fee", "price_monthly", "price_yearly"].map((k) => <td key={k}><input type="number" defaultValue={p[k] ?? ""} placeholder={t("none_set")} onBlur={(e) => e.target.value !== String(p[k] ?? "") && save(p, k, e.target.value)} className="h-9 w-32 rounded-lg border border-slate-200 px-2 font-num text-sm" data-testid={`plan-${p.code}-${k}`} /></td>)}</tr>
        ))}</tbody>
      </table>
    </Card>
  );
}

function PlatformAudit() {
  const { t } = useApp();
  const { data } = useApi("/platform/audit");
  if (!data) return <Spinner />;
  return (
    <Card><CardTitle>{t("audit_logs")}</CardTitle>
      <div className="space-y-2 text-sm">{data.map((a) => <div key={a.id} className="flex flex-wrap gap-2 border-b border-slate-100 py-2"><span className="font-num text-xs text-slate-400">{fmtDateTime(a.at)}</span><b>{a.action}</b><span>{a.entity}</span><span className="text-slate-500">{a.label}</span><span className="ml-auto text-xs text-slate-400">{a.user_email}</span></div>)}</div>
    </Card>
  );
}

export default function Platform() {
  const { t } = useApp();
  return (
    <div data-testid="platform-page">
      <PageHeader eyebrow="FINORA Platform" title={t("platform")} sub={t("platform_note")} />
      <Tabs defaultValue="tenants">
        <TabsList className="h-auto flex-wrap justify-start bg-white/70">{["tenants", "ec_consultant_contracts", "payouts", "email_log", "site_admin", "plans", "audit_logs"].map((k) => <TabsTrigger key={k} value={k} data-testid={`platform-tab-${k}`} className="data-[state=active]:bg-[#071A2B] data-[state=active]:text-white">{t(k)}</TabsTrigger>)}</TabsList>
        <TabsContent value="tenants" className="mt-5"><Tenants /></TabsContent>
        <TabsContent value="ec_consultant_contracts" className="mt-5"><EContractPanel type="FINORA_SAAS" allowCreate title={t("ec_consultant_contracts")} /></TabsContent>
        <TabsContent value="payouts" className="mt-5"><PayoutsPanel /></TabsContent>
        <TabsContent value="email_log" className="mt-5"><EmailLogPanel /></TabsContent>
        <TabsContent value="site_admin" className="mt-5"><SiteAdmin /></TabsContent>
        <TabsContent value="plans" className="mt-5"><Plans /></TabsContent>
        <TabsContent value="audit_logs" className="mt-5"><PlatformAudit /></TabsContent>
      </Tabs>
    </div>
  );
}
