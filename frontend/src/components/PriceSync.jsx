import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";

const EVERY_MS = 3 * 60 * 1000;

export default function PriceSync({ clientId, onChange }) {
  const { t } = useApp();
  const [busy, setBusy] = useState(false);
  const [at, setAt] = useState(null);
  const busyRef = useRef(false);
  const cbRef = useRef(onChange);
  cbRef.current = onChange;

  const run = useCallback(async (manual) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const { data: r } = await api.post(`/assets/prices/sync${clientId ? `?client_id=${clientId}` : ""}`);
      setAt(new Date());
      if (manual) toast.success(`${t("price_refresh_done")}: ${r.updated}${r.linked ? ` / ${t("price_linked")}: ${r.linked}` : ""}${r.skipped ? ` / ${t("price_refresh_skipped")}: ${r.skipped}` : ""}`);
      if (r.updated || r.linked) cbRef.current && cbRef.current();
    } catch (e) {
      if (manual) toast.error(errMsg(e));
    }
    busyRef.current = false;
    setBusy(false);
  }, [clientId, t]);

  useEffect(() => {
    run(false);
    const id = setInterval(() => run(false), EVERY_MS);
    return () => clearInterval(id);
  }, [run]);

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2" data-testid="price-sync-bar">
      <span className={`h-2 w-2 shrink-0 rounded-full ${busy ? "animate-pulse bg-[#C9A227]" : "bg-[#00A878]"}`} />
      <span className="text-xs text-slate-600" data-testid="price-sync-status">
        {busy ? t("price_refreshing") : at ? `${t("price_last_sync")}: ${at.toLocaleTimeString()}` : t("price_auto_on")}
      </span>
      <span className="hidden text-[11px] text-slate-400 sm:inline">{t("price_auto_every")}</span>
      <Button variant="outline" size="sm" className="ml-auto h-8" onClick={() => run(true)} disabled={busy} data-testid="assets-refresh-prices">
        <RefreshCw className={`mr-1 h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />{t("price_refresh")}
      </Button>
    </div>
  );
}
