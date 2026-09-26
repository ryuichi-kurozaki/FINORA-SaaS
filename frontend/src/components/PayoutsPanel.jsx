import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate, yen } from "@/lib/format";
import { Card, CardTitle, Spinner } from "@/components/common";

const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm";

function BankText({ b, t }) {
  if (!b) return <span className="text-xs text-amber-700">{t("pb_not_registered")}</span>;
  return <div className="text-xs leading-5">{b.bank_name}{b.bank_code && `（${b.bank_code}）`} {b.branch_name}{b.branch_code && `（${b.branch_code}）`}<br />{t(`pb_${b.account_type}`)} <span className="font-num">{b.account_number}</span> {b.holder_kana}</div>;
}

function SendDialog({ row, onClose, onDone }) {
  const { t } = useApp();
  const [f, setF] = useState({ transfer_fee: 0, transfer_date: new Date().toISOString().slice(0, 10), note: "" });
  const submit = async () => {
    try { await api.post(`/platform/payouts/${row.payee_id}`, f); toast.success(t("saved")); onDone(); onClose(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={onClose}><DialogContent data-testid="payout-send-dialog">
      <DialogHeader><DialogTitle>{t("po_mark_sent")} — {row.payee_name}</DialogTitle></DialogHeader>
      <BankText b={row.bank} t={t} />
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs">{t("po_transfer_fee")}<input type="number" min={0} className={inp} value={f.transfer_fee} onChange={(e) => setF({ ...f, transfer_fee: Number(e.target.value) })} data-testid="payout-transfer-fee" /></label>
        <label className="text-xs">{t("po_transfer_date")}<input type="date" className={inp} value={f.transfer_date} onChange={(e) => setF({ ...f, transfer_date: e.target.value })} data-testid="payout-transfer-date" /></label>
        <label className="text-xs sm:col-span-2">{t("notes")}<input className={inp} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid="payout-note" /></label>
      </div>
      <div className="rounded-lg bg-slate-50 p-3 text-sm">{t("po_amount")}: <b className="font-num" data-testid="payout-send-amount">{yen(row.total - f.transfer_fee)}</b></div>
      <DialogFooter><Button variant="outline" onClick={onClose}>{t("cancel_action")}</Button><Button className="btn-emerald" disabled={!row.bank || row.total - f.transfer_fee <= 0} onClick={submit} data-testid="payout-send-submit">{t("po_mark_sent")}</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

export default function PayoutsPanel() {
  const { t } = useApp();
  const { data, reload } = useApi("/platform/payouts");
  const [send, setSend] = useState(null);
  if (!data) return <Spinner />;
  return (
    <div className="space-y-6">
      <Card><CardTitle>{t("po_schedule")}</CardTitle>
        <p className="mb-3 text-xs text-slate-500">{t("po_formula")}</p>
        <div className="overflow-x-auto"><table className="data-table w-full min-w-[900px] text-sm" data-testid="payout-table">
          <thead><tr>{["po_payee", "payout_bank", "po_gross", "po_stripe_fee", "po_pending", ""].map((h) => <th key={h}>{h && t(h)}</th>)}</tr></thead>
          <tbody>{data.payees.length === 0 && <tr><td colSpan={6} className="text-center text-xs text-slate-400">—</td></tr>}
            {data.payees.map((r) => (
              <tr key={r.payee_id} data-testid={`payout-row-${r.payee_id}`}>
                <td className="font-medium">{r.payee_name}<div className="text-xs text-slate-400">{r.tenant_name} · {r.payee_email}</div>
                  <details className="mt-1 text-xs"><summary className="cursor-pointer text-slate-500">{t("po_items")} ({r.items.length})</summary>
                    <ul className="mt-1 space-y-0.5 font-num">{r.items.map((i) => <li key={i.payment_id}>{fmtDate(i.date)} {i.invoice_number} {yen(i.amount)} − {t("po_stripe_fee")} {yen(i.stripe_fee)}{i.fee_estimated ? "*" : ""}{i.refunded ? ` − ${t("po_refunded")} ${yen(i.refunded)}` : ""}{i.settled ? ` − ${t("po_settled")} ${yen(i.settled)}` : ""} = {yen(i.pending)}</li>)}</ul></details></td>
                <td><BankText b={r.bank} t={t} /></td>
                <td className="font-num">{yen(r.gross)}</td><td className="font-num">{yen(r.fees)}</td>
                <td className="font-num font-semibold" data-testid={`payout-pending-${r.payee_id}`}>{yen(r.total)}</td>
                <td><Button size="sm" className="btn-emerald" disabled={!r.bank || r.total <= 0} onClick={() => setSend(r)} data-testid={`payout-send-${r.payee_id}`}>{t("po_mark_sent")}</Button></td>
              </tr>))}</tbody>
        </table></div>
        <p className="mt-2 text-[11px] text-slate-400">{t("po_fee_est_note")}</p>
      </Card>
      <Card><CardTitle>{t("po_history")}</CardTitle>
        <div className="overflow-x-auto"><table className="data-table w-full min-w-[700px] text-sm" data-testid="payout-history-table">
          <thead><tr>{["po_transfer_date", "po_payee", "po_pending", "po_transfer_fee", "po_amount", "notes"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
          <tbody>{data.history.map((h) => <tr key={h.id}><td className="font-num text-xs">{fmtDate(h.transfer_date)}</td><td>{h.payee_name || h.tenant_name}</td><td className="font-num">{yen(h.total)}</td><td className="font-num">{yen(h.transfer_fee)}</td><td className="font-num font-semibold">{yen(h.amount)}</td><td className="text-xs">{h.note}</td></tr>)}</tbody>
        </table></div>
      </Card>
      {send && <SendDialog row={send} onClose={() => setSend(null)} onDone={reload} />}
    </div>
  );
}
