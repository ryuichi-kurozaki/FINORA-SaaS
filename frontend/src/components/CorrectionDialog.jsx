import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";

const area = "w-full rounded-lg border border-slate-200 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40";

export default function CorrectionDialog({ open, onOpenChange, clientId, entity, targetId, targetLabel, onDone }) {
  const { t } = useApp();
  const [f, setF] = useState({ reason: "", requested_change: "", comment: "", due_date: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async () => {
    if (!f.reason || !f.requested_change) return toast.error(`${t("reason")} / ${t("requested_change")}: required`);
    try {
      await api.post("/corrections", { client_id: clientId, target_entity: entity, target_id: targetId, target_label: targetLabel, ...f, due_date: f.due_date || null });
      toast.success(t("saved")); setF({ reason: "", requested_change: "", comment: "", due_date: "" }); onOpenChange(false); onDone && onDone();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="correction-dialog">
        <DialogHeader><DialogTitle className="font-display">{t("request_correction")}</DialogTitle></DialogHeader>
        <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">{t("target")}: <b className="text-[#071A2B]">{t(entity === "portfolio" ? "portfolio_target" : entity)}</b>{targetLabel && ` — ${targetLabel}`}</div>
        <div className="space-y-3">
          <label className="block text-xs font-medium text-slate-600">{t("reason")} *<textarea rows={2} className={`${area} mt-1`} value={f.reason} onChange={set("reason")} data-testid="correction-reason" /></label>
          <label className="block text-xs font-medium text-slate-600">{t("requested_change")} *<textarea rows={2} className={`${area} mt-1`} value={f.requested_change} onChange={set("requested_change")} data-testid="correction-change" /></label>
          <label className="block text-xs font-medium text-slate-600">{t("comment")}<textarea rows={2} className={`${area} mt-1`} value={f.comment} onChange={set("comment")} data-testid="correction-comment" /></label>
          <label className="block text-xs font-medium text-slate-600">{t("due_date")}<input type="date" className="mt-1 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm" value={f.due_date} onChange={set("due_date")} data-testid="correction-due" /></label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t("cancel")}</Button>
          <Button className="btn-emerald" onClick={submit} data-testid="correction-submit">{t("send")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
