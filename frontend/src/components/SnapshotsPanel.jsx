import { useState } from "react";
import { Camera } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { yen, plColor } from "@/lib/format";
import { Card, CardTitle, Empty } from "@/components/common";

export default function SnapshotsPanel({ clientId, current }) {
  const { t } = useApp();
  const { data, reload } = useApi(clientId ? `/snapshots?client_id=${clientId}` : null, [clientId]);
  const [label, setLabel] = useState("");
  const save = async () => {
    try { await api.post("/snapshots", { client_id: clientId, label }); setLabel(""); toast.success(t("saved")); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card data-testid="snapshots-panel">
      <CardTitle>{t("snapshots")}</CardTitle>
      {!clientId ? <Empty text={t("select_client_first")} /> : (
        <>
          <div className="mb-4 flex gap-2">
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={t("snapshot_label")} className="h-10 flex-1 rounded-lg border border-slate-200 px-3 text-sm" data-testid="snapshot-label" />
            <Button className="btn-emerald h-10" onClick={save} data-testid="snapshot-save-btn"><Camera className="mr-1 h-4 w-4" />{t("save_snapshot")}</Button>
          </div>
          <div className="-mx-2 overflow-x-auto">
            <table className="data-table w-full min-w-[640px] text-sm">
              <thead><tr>{["date", "snapshot_label", "total_assets", "total_liabilities", "net_worth", "vs_current"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
              <tbody>
                {(data || []).map((s) => {
                  const diff = current ? current.net_worth - s.totals.net_worth : 0;
                  return (
                    <tr key={s.id} data-testid={`snapshot-${s.id}`}>
                      <td className="font-num">{s.date}</td><td>{s.label || "—"} <span className="text-[10px] text-slate-400">{s.created_by_name}</span></td>
                      <td className="font-num">{yen(s.totals.total_assets)}</td><td className="font-num">{yen(s.totals.total_liabilities)}</td>
                      <td className="font-num font-semibold">{yen(s.totals.net_worth)}</td><td className={`font-num ${plColor(diff)}`}>{diff >= 0 ? "+" : ""}{yen(diff)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
