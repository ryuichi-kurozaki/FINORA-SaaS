import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { num } from "@/lib/format";
import { Card, CardTitle, PageHeader } from "@/components/common";
import { useScopeLabel } from "@/lib/useDashboard";
import EntityManager from "@/components/EntityManager";
import TxSync from "@/components/TxSync";

export function PositionsTable({ clientId }) {
  const { t } = useApp();
  const { data } = useApi(`/positions${clientId ? `?client_id=${clientId}` : ""}`, [clientId]);
  const cols = ["asset_name", "holding_qty", "avg_cost", "cost_basis", "market_value", "unrealized_pl", "realized_pl", "dividends_cum", "interest_cum"];
  return (
    <Card data-testid="positions-table">
      <CardTitle>{t("positions")}</CardTitle>
      <div className="-mx-2 overflow-x-auto">
        <table className="data-table w-full min-w-[900px] text-sm">
          <thead><tr>{cols.map((c) => <th key={c}>{t(c)}</th>)}</tr></thead>
          <tbody>
            {(data || []).map((p) => (
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
  return (
    <div className="space-y-6" data-testid="transactions-page">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <PageHeader eyebrow={`Transactions · ${scope}`} title={t("transactions")} />
        <TxSync clientId={scopeClient} />
      </div>
      <PositionsTable clientId={scopeClient} />
      <EntityManager key={scopeClient} entity="transactions" />
    </div>
  );
}
