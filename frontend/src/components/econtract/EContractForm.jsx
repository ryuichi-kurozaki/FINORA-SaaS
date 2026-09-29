import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";

const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm";
const today = () => new Date().toISOString().slice(0, 10);
const DEF = { ja: { s: "コンサルティングサービス", d: "月次の資産運用に関するコンサルティングおよび助言業務。詳細は別途協議のうえ定めるものとする。（仮入力：後で編集してください）" },
  en: { s: "Consulting service", d: "Monthly asset management consulting and advisory services. Details to be agreed separately. (draft — edit later)" },
  pt: { s: "Serviço de consultoria", d: "Consultoria e assessoria mensal de gestão de ativos. Detalhes a combinar separadamente. (rascunho — edite depois)" } };

export default function EContractForm({ type, clientId, prefill, requestId, onClose, onDone }) {
  const { t, lang, clients } = useApp();
  const saas = type === "FINORA_SAAS";
  const { data: tenants } = useApi(saas ? "/platform/tenants" : null);
  const { data: plans } = useApi(saas ? "/platform/plans" : null);
  const [f, setF] = useState({ tenant_id: "", client_id: "", lang: lang || "ja", service_name: saas ? "FINORA SaaS" : (DEF[lang] || DEF.ja).s, description: saas ? "" : (DEF[lang] || DEF.ja).d, fee_type: "MONTHLY", fee: 0, tax_mode: "exclusive",
    tax_rate: 10, start_date: today(), end_date: "", billing_day: 1, payment_terms_days: 30, auto_renew: true, plan_code: "STANDARD", ...(prefill || {}) });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const save = async () => {
    const terms = { ...f, fee: Number(f.fee), tax_rate: Number(f.tax_rate), billing_day: Number(f.billing_day), payment_terms_days: Number(f.payment_terms_days), end_date: f.end_date || null };
    ["tenant_id", "client_id", "lang"].forEach((k) => delete terms[k]);
    try {
      const { data } = await api.post("/econtracts", { contract_type: type, client_id: clientId || f.client_id || null, tenant_id: f.tenant_id || null, lang: f.lang, terms, request_id: requestId || null });
      toast.success(t("saved")); onDone(data.id);
    } catch (e) { toast.error(errMsg(e)); }
  };
  const L = (k, el) => <label className="text-xs text-slate-600">{t(k)}{el}</label>;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="econtract-form">
        <DialogHeader><DialogTitle>{t(saas ? "ec_new_saas" : "ec_new")}</DialogTitle></DialogHeader>
        <div className="grid max-h-[65vh] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
          {!saas && !clientId && L("client", <select className={inp} value={f.client_id} onChange={set("client_id")} data-testid="ec-client">
            <option value="">—</option>{(clients || []).map((c) => <option key={c.id} value={c.id}>{c.corporate_name || c.name}</option>)}</select>)}
          {saas && L("tenants", <select className={inp} value={f.tenant_id} onChange={set("tenant_id")} data-testid="ec-tenant">
            <option value="">—</option>{(tenants || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>)}
          {saas && L("plan", <select className={inp} value={f.plan_code} onChange={set("plan_code")} data-testid="ec-plan">
            {(plans || []).map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select>)}
          {L("ec_service", <input className={inp} value={f.service_name} onChange={set("service_name")} placeholder={(DEF[lang] || DEF.ja).s} data-testid="ec-service" />)}
          {L("ec_doc_lang", <select className={inp} value={f.lang} onChange={set("lang")} data-testid="ec-lang"><option value="ja">日本語</option><option value="en">English</option><option value="pt">Português</option></select>)}
          <label className="text-xs text-slate-600 sm:col-span-2">{t("description")}<textarea className={`${inp} h-20 py-2`} value={f.description} onChange={set("description")} placeholder={(DEF[lang] || DEF.ja).d} data-testid="ec-description" /></label>
          {!saas && L("ec_fee", <input type="number" min="0" className={inp} value={f.fee} onChange={set("fee")} data-testid="ec-fee" />)}
          {!saas && L("ec_cycle", <select className={inp} value={f.fee_type} onChange={set("fee_type")} data-testid="ec-cycle">{["MONTHLY", "YEARLY", "ONE_TIME", "HOURLY"].map((x) => <option key={x} value={x}>{t(`cyc_${x}`)}</option>)}</select>)}
          {!saas && L("ec_tax", <select className={inp} value={f.tax_mode} onChange={set("tax_mode")} data-testid="ec-tax">{["exclusive", "inclusive", "exempt"].map((x) => <option key={x} value={x}>{t(`tax_${x}`)}</option>)}</select>)}
          {!saas && L("ec_billing_day", <input type="number" min="1" max="28" className={inp} value={f.billing_day} onChange={set("billing_day")} data-testid="ec-billing-day" />)}
          {L("ec_start", <input type="date" className={inp} value={f.start_date} onChange={set("start_date")} data-testid="ec-start" />)}
          {L("ec_end", <input type="date" className={inp} value={f.end_date} onChange={set("end_date")} data-testid="ec-end" />)}
          <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={f.auto_renew} onChange={set("auto_renew")} data-testid="ec-auto-renew" />{t("ec_auto_renew")}</label>
        </div>
        <DialogFooter><Button className="btn-emerald" disabled={!f.service_name || (saas && !f.tenant_id) || (!saas && !clientId && !f.client_id)} onClick={save} data-testid="ec-save">{t("ec_create_draft")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
