import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { fmtDate, num } from "@/lib/format";
import { Empty } from "@/components/common";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export default function TxHistoryDialog({ assetId, assetName, txs, onClose }) {
  const { t } = useApp();
  const { data: accounts } = useApi("/data/accounts", []);
  const accMap = Object.fromEntries((accounts || []).map((a) => [a.id, a.institution]));
  const rows = (txs || []).filter((x) => x.asset_id === assetId)
    .sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  return (
    <Dialog open={!!assetId} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto" data-testid="tx-history-dialog">
        <DialogHeader><DialogTitle className="font-display">{t("tx_history")} — {assetName}</DialogTitle></DialogHeader>
        {rows.length === 0 ? <Empty text={t("tx_history_empty")} /> : (
          <div className="-mx-2 overflow-x-auto">
            <table className="data-table w-full min-w-[600px] text-sm">
              <thead><tr>{["date", "account_id", "tx_type", "quantity", "unit_price", "amount"].map((c) => <th key={c}>{t(c)}</th>)}</tr></thead>
              <tbody>
                {rows.map((x) => (
                  <tr key={x.id} data-testid={`tx-history-row-${x.id}`}>
                    <td className="font-num text-slate-600">{fmtDate(x.date)}</td>
                    <td className="whitespace-nowrap text-slate-700">{accMap[x.account_id] || "—"}</td>
                    <td><span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{t(x.tx_type)}</span></td>
                    <td className="font-num">{num(x.quantity, 4)}</td>
                    <td className="font-num">{num(x.unit_price, 2)}</td>
                    <td className="font-num font-medium">{num(x.amount, 2)} <span className="text-[11px] text-slate-400">{x.currency}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
