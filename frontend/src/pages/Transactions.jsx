import { useMemo, useState } from "react";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { num } from "@/lib/format";
import { Card, CardTitle, PageHeader } from "@/components/common";
import { useScopeLabel } from "@/lib/useDashboard";
import EntityManager from "@/components/EntityManager";
import TxSync from "@/components/TxSync";

export function PositionsTable({ clientId, accountId, assetAcct }) {
  const { t } = useApp();
  const { data } = useApi(`/positions${clientId ? `?client_id=${clientId}` : ""}`, [clientId]);
  const cols = ["asset_name", "holding_qty", "avg_cost", "cost_basis", "market_value", "unrealized_pl", "realized_pl", "dividends_cum", "interest_cum"];
  const rows = (data || []).filter((p) => !accountId ? true : accountId === "none" ? !(assetAcct && assetAcct[p.asset_id]) : (assetAcct && assetAcct[p.asset_id]) === accountId);
  return (
    <Card data-testid="positions-table">
      <CardTitle>{t("positions")}</CardTitle>
      <div className="-mx-2 overflow-x-auto">
        <table className="data-table w-full min-w-[900px] text-sm">
          <thead><tr>{cols.map((c) => <th key={c}>{t(c)}</th>)}</tr></thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.asset_id} data-testid={`position-${p.asset_id}`}>
                <td className="font-medium">{p.asset_name} <span className="text-[11px] text-slate-400">{p.currency}</span>{p.qty_mismatch && <span className="ml-2 rounded bg-red-50 px-1.5 text-[10px] text-red-600">{t("qty_mismatch")}</span>}</td>
                {[p.qty, p.avg_cost, p.cost, p.market_value].map((v, i) => <td key={i} className="font-num">{num(v, 2)}</td>)}
                {[p.unrealized, p.realized].map((v, i) => <td key={i} className={`font-num ${v >= 0 ? "text-[#00A878]" : "text-red-600"}`}>{num(v, 2)}</td>)}
                <td className="font-num">{num(p.dividends, 2)}</td><td className="font-num">{num(p.interest, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[10px] text-slate-400">CALCULATION · {t("avg_cost")} = {t("cost_basis")} ÷ {t("holding_qty")}</p>
    </Card>
  );
}

export default function Transactions() {
  const { t, scopeClient } = useApp();
  const scope = useScopeLabel();
  const [acct, setAcct] = useState("");
  const { data: accounts } = useApi(`/data/accounts${scopeClient ? `?client_id=${scopeClient}` : ""}`, [scopeClient]);
  const { data: assets } = useApi(`/data/assets${scopeClient ? `?client_id=${scopeClient}` : ""}`, [scopeClient]);
  const assetAcct = useMemo(() => Object.fromEntries((assets || []).map((a) => [a.id, a.account_id])), [assets]);
  const hasOrphan = (assets || []).some((a) => !a.account_id);
  return (
    <div className="space-y-6" data-testid="transactions-page">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <PageHeader eyebrow={`Transactions · ${scope}`} title={t("transactions")} />
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-slate-500">{t("account_id")}</span>
          <select value={acct} onChange={(e) => setAcct(e.target.value)} data-testid="transactions-account-select"
            className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40">
            <option value="">{t("all_accounts")}</option>
            {(accounts || []).map((a) => <option key={a.id} value={a.id}>{a.institution}{a.currency ? ` (${a.currency})` : ""}</option>)}
            {hasOrphan && <option value="none">{t("account_unassigned")}</option>}
          </select>
          <TxSync clientId={scopeClient} />
        </div>
      </div>
      <PositionsTable clientId={scopeClient} accountId={acct} assetAcct={assetAcct} />
      <EntityManager key={scopeClient} entity="transactions" accountFilter={acct} />
    </div>
  );
}
