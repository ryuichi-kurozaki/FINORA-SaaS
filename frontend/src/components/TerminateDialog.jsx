import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";

const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-200";

export default function TerminateDialog({ path, title, desc, onClose, onDone, testid = "terminate" }) {
  const { t } = useApp();
  const [f, setF] = useState({ end_date: new Date().toISOString().slice(0, 10), reason: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await api.post(path, f);
      toast.success(t("term_done"));
      onDone && onDone();
      onClose();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md" data-testid={`${testid}-dialog`}>
        <DialogHeader><DialogTitle className="font-display text-red-700">{title}</DialogTitle></DialogHeader>
        <p className="rounded-lg bg-red-50 p-3 text-xs leading-relaxed text-red-700">{desc}</p>
        <label className="block text-xs font-medium text-slate-600">{t("term_date")}
          <input type="date" className={inp} value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} data-testid={`${testid}-date`} /></label>
        <label className="block text-xs font-medium text-slate-600">{t("ec_end_reason")}<span className="text-red-500"> *</span>
          <textarea rows={3} className={`${inp} h-auto py-2`} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid={`${testid}-reason`} /></label>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid={`${testid}-cancel`}>{t("cancel")}</Button>
          <Button className="bg-red-600 text-white hover:bg-red-700" disabled={busy || !f.reason.trim() || !f.end_date} onClick={submit} data-testid={`${testid}-submit`}>{t("term_submit")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
