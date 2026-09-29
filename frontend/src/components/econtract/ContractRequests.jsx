import { useState } from "react";
import { FileSignature } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, CardTitle, Empty } from "@/components/common";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import EContractForm from "./EContractForm";

const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm";
const TONE = { PENDING: "bg-amber-50 text-amber-700", APPROVED: "bg-emerald-50 text-emerald-700", REJECTED: "bg-red-50 text-red-600", WITHDRAWN: "bg-slate-100 text-slate-500" };

function RequestForm({ onClose, onDone }) {
  const { t, lang } = useApp();
  const [f, setF] = useState({ service_name: "", note: "", start_date: "", fee_type: "MONTHLY", lang: lang || "ja" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    try { await api.post("/contract-requests", { ...f, start_date: f.start_date || null }); toast.success(t("cr_sent")); onDone(); onClose(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="cr-form">
        <DialogHeader><DialogTitle>{t("cr_new")}</DialogTitle></DialogHeader>
        <div className="grid gap-3">
          <label className="text-xs text-slate-600">{t("cr_service")}
            <input className={inp} value={f.service_name} onChange={set("service_name")} placeholder={t("cr_service_ph")} data-testid="cr-service" /></label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-slate-600">{t("cr_start")}
              <input type="date" className={inp} value={f.start_date} onChange={set("start_date")} data-testid="cr-start" /></label>
            <label className="text-xs text-slate-600">{t("ec_cycle")}
              <select className={inp} value={f.fee_type} onChange={set("fee_type")} data-testid="cr-cycle">
                {["MONTHLY", "YEARLY", "ONE_TIME", "HOURLY"].map((x) => <option key={x} value={x}>{t(`cyc_${x}`)}</option>)}</select></label>
          </div>
          <label className="text-xs text-slate-600">{t("cr_note")}
            <textarea className={`${inp} h-24 py-2`} value={f.note} onChange={set("note")} placeholder={t("cr_note_ph")} data-testid="cr-note" /></label>
          <p className="text-[11px] leading-relaxed text-slate-400">{t("cr_hint")}</p>
        </div>
        <DialogFooter><Button className="btn-emerald" disabled={!f.service_name} onClick={save} data-testid="cr-save">{t("cr_submit")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ContractRequests({ clientId }) {
  const { t, user } = useApp();
  const isClient = user.role === "client";
  const [open, setOpen] = useState(false);
  const [approve, setApprove] = useState(null);
  const { data, reload } = useApi(`/contract-requests${clientId ? `?client_id=${clientId}` : ""}`);
  const rows = data || [];
  const act = async (r, path, body) => {
    try { await api.post(`/contract-requests/${r.id}/${path}`, body || {}); toast.success(t("saved")); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const pending = rows.filter((r) => r.status === "PENDING");
  return (
    <Card data-testid="contract-requests">
      <CardTitle right={isClient && <Button className="btn-emerald" onClick={() => setOpen(true)} disabled={!!pending.length} data-testid="cr-new-btn">
        <FileSignature className="mr-1 h-4 w-4" />{t("cr_new")}</Button>}>
        {t("cr_title")}{!isClient && pending.length ? <span className="ml-2 rounded-md bg-amber-50 px-1.5 py-0.5 text-[11px] font-semibold text-amber-700" data-testid="cr-pending-count">{pending.length}</span> : null}
      </CardTitle>
      {!rows.length ? <Empty text={t("cr_empty")} /> : (
        <div className="overflow-x-auto"><table className="data-table w-full text-sm">
          <thead><tr>{[...(isClient ? [] : ["client"]), "cr_service", "cr_start", "ec_cycle", "cr_note", "status", ""].map((h, k) => <th key={k}>{h && t(h)}</th>)}</tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id} data-testid={`cr-row-${r.id}`}>
              {!isClient && <td>{r.client_name}</td>}
              <td>{r.service_name}</td>
              <td className="font-num text-xs">{r.start_date ? fmtDate(r.start_date) : "—"}</td>
              <td className="text-xs">{t(`cyc_${r.fee_type}`)}</td>
              <td className="max-w-[260px] whitespace-pre-wrap text-xs text-slate-500">{r.note || "—"}{r.reject_reason && <div className="mt-1 text-red-600">{t("cr_reject_reason")}: {r.reject_reason}</div>}</td>
              <td><span className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${TONE[r.status]}`} data-testid={`cr-status-${r.id}`}>{t(`cr_${r.status}`)}</span>
                {r.econtract_number && <div className="font-num text-[10px] text-slate-400">{r.econtract_number}</div>}</td>
              <td className="whitespace-nowrap">
                {r.status === "PENDING" && !isClient && <span className="flex gap-2">
                  <Button size="sm" className="btn-emerald" onClick={() => setApprove(r)} data-testid={`cr-approve-${r.id}`}>{t("cr_approve")}</Button>
                  <Button size="sm" variant="outline" onClick={() => { const reason = window.prompt(t("cr_reject_reason")); if (reason !== null) act(r, "reject", { reason }); }} data-testid={`cr-reject-${r.id}`}>{t("cr_reject")}</Button>
                </span>}
                {r.status === "PENDING" && isClient && <Button size="sm" variant="outline" onClick={() => act(r, "withdraw")} data-testid={`cr-withdraw-${r.id}`}>{t("cr_withdraw")}</Button>}
              </td>
            </tr>))}</tbody>
        </table></div>
      )}
      {open && <RequestForm onClose={() => setOpen(false)} onDone={reload} />}
      {approve && <EContractForm type="CONSULTING" clientId={approve.client_id} requestId={approve.id}
        prefill={{ service_name: approve.service_name, description: approve.note || "", fee_type: approve.fee_type, lang: approve.lang, ...(approve.start_date ? { start_date: approve.start_date } : {}) }}
        onClose={() => setApprove(null)} onDone={(id) => { reload(); window.location.assign(`/econtracts/${id}`); }} />}
    </Card>
  );
}
