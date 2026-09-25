import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { yen } from "@/lib/format";
import { Card, CardTitle, Spinner } from "@/components/common";

const FIELDS = ["company_name", "representative", "address", "phone", "email", "registration_no", "bank_info", "invoice_note"];

function BillingProfile() {
  const { t } = useApp();
  const { data } = useApi("/billing/profile");
  const [f, setF] = useState({});
  useEffect(() => { if (data) setF(data); }, [data]);
  const save = async () => { try { await api.put("/billing/profile", f); toast.success(t("saved")); } catch (e) { toast.error(errMsg(e)); } };
  if (!data) return <Spinner />;
  return (
    <Card><CardTitle>{t("billing_profile")}</CardTitle>
      <div className="grid gap-3 sm:grid-cols-2">
        {FIELDS.map((k) => <label key={k} className={`text-xs text-slate-600 ${["bank_info", "invoice_note"].includes(k) ? "sm:col-span-2" : ""}`}>{t(k === "email" ? "email" : k)}
          {["bank_info", "invoice_note"].includes(k) ? <textarea rows={2} value={f[k] || ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 p-2 text-sm" data-testid={`bp-${k}`} />
            : <input value={f[k] || ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="mt-1 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm" data-testid={`bp-${k}`} />}</label>)}
      </div>
      <Button className="btn-emerald mt-4" onClick={save} data-testid="bp-save">{t("save")}</Button>
    </Card>
  );
}

function Subscription() {
  const { t } = useApp();
  const { data } = useApi("/subscription");
  if (!data) return <Spinner />;
  const s = data.subscription || {};
  return (
    <Card><CardTitle>{t("subscription")}</CardTitle>
      <dl className="grid grid-cols-2 gap-2 text-sm" data-testid="subscription-card">
        <dt className="text-slate-500">{t("company_name")}</dt><dd>{data.tenant.name}</dd>
        <dt className="text-slate-500">{t("status")}</dt><dd>{t(data.tenant.status || "ACTIVE")}</dd>
        <dt className="text-slate-500">{t("plan")}</dt><dd>{data.plan?.name || s.plan_code}</dd>
        <dt className="text-slate-500">{t("start_date_c")}</dt><dd className="font-num">{s.start_date || "—"}</dd>
        <dt className="text-slate-500">{t("renewal_date")}</dt><dd className="font-num">{s.renewal_date || "—"}</dd>
        <dt className="text-slate-500">{t("amount")}</dt><dd className="font-num">{s.amount != null ? yen(s.amount) : t("none_set")}</dd>
        <dt className="text-slate-500">{t("payment_status")}</dt><dd>{s.payment_status || "—"}</dd>
      </dl>
      <p className="mt-3 text-[11px] text-slate-500">{t("saas_separate_note")}</p>
    </Card>
  );
}

export default function TenantSettings() {
  return <div className="grid gap-6 xl:grid-cols-2"><BillingProfile /><Subscription /></div>;
}
