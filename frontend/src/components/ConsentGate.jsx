import { useState } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";

export default function ConsentGate() {
  const { t } = useApp();
  const { data, reload } = useApi("/consents/status");
  const [checked, setChecked] = useState({});
  const req = data?.required || [];
  if (!req.length) return null;
  const all = req.every((r) => checked[r.doc]);
  const agree = async () => {
    try { await api.post("/consents", { docs: req.map((r) => r.doc) }); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open>
      <DialogContent className="max-w-md [&>button]:hidden" data-testid="consent-gate">
        <DialogHeader><DialogTitle className="flex items-center gap-2 font-display"><ShieldCheck className="h-5 w-5 text-[#00A878]" />{t("consent_title")}</DialogTitle></DialogHeader>
        <div className="space-y-2">
          {req.map((r) => (
            <label key={r.doc} className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm">
              <input type="checkbox" checked={!!checked[r.doc]} onChange={(e) => setChecked({ ...checked, [r.doc]: e.target.checked })} className="h-4 w-4 accent-[#00A878]" data-testid={`consent-check-${r.doc}`} />
              <span className="flex-1">{t(`consent_${r.doc}`)}</span><span className="font-num text-[11px] text-slate-400">v{r.version}</span>
            </label>
          ))}
        </div>
        <Link to="/legal" target="_blank" className="text-xs text-[#00A878] underline">{t("terms")} / {t("privacy")}</Link>
        <div><Button className="btn-emerald w-full" disabled={!all} onClick={agree} data-testid="consent-agree-btn">{t("agree_all")}</Button></div>
      </DialogContent>
    </Dialog>
  );
}
