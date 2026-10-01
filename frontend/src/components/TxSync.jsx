import { useState } from "react";
import { ArrowLeftRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";

export default function TxSync({ clientId }) {
  const { t } = useApp();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/txlink/rebuild${clientId ? `?client_id=${clientId}` : ""}`);
      toast.success(`${t("tx_sync_done")} · ${t("tx_count")}: ${data.linked} / ${t("holdings")}: ${data.rebuilt}`);
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  return (
    <Button variant="outline" size="sm" className="h-8" onClick={run} disabled={busy} data-testid="tx-sync-btn">
      <ArrowLeftRight className={`mr-1 h-3.5 w-3.5 ${busy ? "animate-pulse" : ""}`} />{t("tx_sync_portfolio")}
    </Button>
  );
}
