import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Landmark } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate, yen } from "@/lib/format";
import { Card, CardTitle, Spinner } from "@/components/common";

const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm";
const EMPTY = { bank_name: "", bank_code: "", branch_name: "", branch_code: "", account_type: "ORDINARY", account_number: "", holder_kana: "" };
const TEXT = [["bank_name", "pb_bank_name"], ["bank_code", "pb_bank_code"], ["branch_name", "pb_branch_name"], ["branch_code", "pb_branch_code"], ["account_number", "pb_account_number"], ["holder_kana", "pb_holder_kana"]];

function BankForm() {
  const { t } = useApp();
  const { data } = useApi("/payouts/bank");
  const [f, setF] = useState(EMPTY);
  useEffect(() => { if (data?.bank) setF({ ...EMPTY, ...data.bank }); }, [data]);
  const save = async () => { try { await api.put("/payouts/bank", f); toast.success(t("saved")); } catch (e) { toast.error(errMsg(e)); } };
  if (!data) return <Spinner />;
  return (
    <Card data-testid="payout-bank-card"><CardTitle right={<span className={`rounded-md px-2 py-0.5 text-[11px] ${data.bank ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`} data-testid="payout-bank-status">{t(data.bank ? "pb_registered" : "pb_not_registered")}</span>}>
      <span className="inline-flex items-center gap-2"><Landmark className="h-4 w-4 text-[#00A878]" />{t("payout_bank")}</span></CardTitle>
      <p className="mb-3 text-xs leading-relaxed text-slate-500">{t("pb_note")}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {TEXT.map(([k, l]) => <label key={k} className="text-xs text-slate-600">{t(l)}<input value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value.trim() === "" ? "" : e.target.value })} className={inp} data-testid={`pb-${k}`} /></label>)}
        <label className="text-xs text-slate-600">{t("pb_account_type")}
          <select value={f.account_type} onChange={(e) => setF({ ...f, account_type: e.target.value })} className={inp} data-testid="pb-account_type">
            {["ORDINARY", "CHECKING", "SAVINGS"].map((k) => <option key={k} value={k}>{t(`pb_${k}`)}</option>)}</select></label>
      </div>
      <Button className="btn-emerald mt-4" onClick={save} data-testid="pb-save">{t("save")}</Button>
    </Card>
  );
}

function PayoutStatus() {
  const { t } = useApp();
  const { data } = useApi("/payouts");
  if (!data) return <Spinner />;
  const p = data.pending;
  return (
    <Card data-testid="payout-status-card"><CardTitle>{t("payout_status")}</CardTitle>
      <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-4">
        <div className="text-xs text-slate-500">{t("po_pending")}</div>
        <div className="font-num text-2xl font-semibold text-[#071A2B]" data-testid="payout-pending-total">{yen(p.total)}</div>
        <div className="mt-1 text-[11px] text-slate-500">{t("po_formula")}</div>
      </div>
      <div className="mt-4 text-xs font-medium text-slate-600">{t("po_history")}</div>
      <ul className="mt-2 space-y-1.5 text-sm" data-testid="payout-history">
        {data.history.length === 0 && <li className="text-xs text-slate-400">—</li>}
        {data.history.map((h) => <li key={h.id} className="flex justify-between border-b border-slate-100 pb-1.5"><span className="font-num text-xs">{fmtDate(h.transfer_date)}</span><span className="font-num">{yen(h.amount)}<span className="ml-2 text-[10px] text-slate-400">{t("po_transfer_fee")} {yen(h.transfer_fee)}</span></span></li>)}
      </ul>
    </Card>
  );
}

export default function PayoutSettings() {
  return <><BankForm /><PayoutStatus /></>;
}
