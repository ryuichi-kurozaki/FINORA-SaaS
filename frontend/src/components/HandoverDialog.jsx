import { useMemo, useState } from "react";
import { ArrowRightLeft } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";

const sel = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm";

export default function HandoverDialog() {
  const { t, user, clients, refreshClients: reloadClients } = useApp();
  const mine = !!user.is_consultant;
  const [open, setOpen] = useState(false);
  const { data: users } = useApi("/users");
  const staff = (users || []).filter((u) => ["admin", "consultant"].includes(u.role) && u.active !== false);
  const [from, setFrom] = useState(mine ? user.id : "");
  const [to, setTo] = useState("");
  const [picked, setPicked] = useState(null);
  const list = useMemo(() => clients.filter((c) => c.consultant_id === from), [clients, from]);
  const ids = picked ?? list.map((c) => c.id);
  const toggle = (id) => setPicked(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  const go = async () => {
    try {
      const { data } = await api.post("/clients/reassign", { from_id: from, to_id: to, client_ids: ids });
      toast.success(`${t("handover_done")} (${data.moved})`); setOpen(false); setPicked(null); reloadClients?.();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)} data-testid="handover-open-btn"><ArrowRightLeft className="mr-1.5 h-4 w-4" />{t("handover")}</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="handover-dialog">
          <DialogHeader><DialogTitle>{t("handover_title")}</DialogTitle></DialogHeader>
          <div className="grid gap-3 text-xs text-slate-600 sm:grid-cols-2">
            <label>{t("from_consultant")}<select className={sel} value={from} disabled={mine} onChange={(e) => { setFrom(e.target.value); setPicked(null); }} data-testid="handover-from">
              <option value="">—</option>{staff.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
            <label>{t("to_consultant")}<select className={sel} value={to} onChange={(e) => setTo(e.target.value)} data-testid="handover-to">
              <option value="">—</option>{staff.filter((u) => u.id !== from).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
          </div>
          <div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-slate-100 p-2" data-testid="handover-client-list">
            {!list.length ? <div className="p-2 text-xs text-slate-400">{t("no_data")}</div> : list.map((c) => (
              <label key={c.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-slate-50">
                <input type="checkbox" checked={ids.includes(c.id)} onChange={() => toggle(c.id)} data-testid={`handover-client-${c.id}`} />{c.corporate_name || c.name}
              </label>))}
          </div>
          {mine && <p className="text-[11px] text-amber-700">{t("handover_mine_note")}</p>}
          <DialogFooter><Button className="btn-emerald" disabled={!from || !to || !ids.length} onClick={go} data-testid="handover-submit">{t("handover_do")} ({ids.length})</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
