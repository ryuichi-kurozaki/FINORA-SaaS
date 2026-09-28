import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { fmtDate, yen } from "@/lib/format";
import TerminateDialog from "@/components/TerminateDialog";
import { StatusPill } from "./EContractPanel";

export default function LegacyContracts({ clientId }) {
  const { t, isClient, clientName } = useApp();
  const { data, reload } = useApi(`/contracts/legacy${clientId ? `?client_id=${clientId}` : ""}`, [clientId]);
  const [term, setTerm] = useState(null);
  if (!data || !data.length) return null;
  return (
    <div className="mt-6" data-testid="legacy-contracts">
      <div className="mb-2 text-xs font-semibold text-slate-500">{t("legacy_contracts")} ({data.length})</div>
      <div className="overflow-x-auto"><table className="data-table w-full text-sm">
        <thead><tr>{["client", "ec_service", "status", "ec_start", "ec_end", "ec_fee", ""].map((h, i) => <th key={i}>{h && t(h)}</th>)}</tr></thead>
        <tbody>{data.map((r) => (
          <tr key={r.id} data-testid={`legacy-row-${r.id}`}>
            <td>{clientName(r.client_id)}</td><td>{r.name}<div className="text-[11px] text-slate-400">{r.service_name}</div></td>
            <td><StatusPill s={r.status} t={t} />{r.end_reason && <div className="mt-1 max-w-[200px] truncate text-[11px] text-slate-400" title={r.end_reason}>{r.end_reason}</div>}</td>
            <td className="font-num text-xs">{fmtDate(r.start_date)}</td><td className="font-num text-xs">{fmtDate(r.end_date)}</td>
            <td className="font-num">{yen(r.fee)}<div className="text-[10px] text-slate-400">{t(`cyc_${r.fee_type}`)}</div></td>
            <td className="text-right">{!isClient && !["ENDED", "CANCELLED"].includes(r.status) &&
              <Button size="sm" variant="outline" className="text-red-600" onClick={() => setTerm(r)} data-testid={`legacy-terminate-${r.id}`}>{t("term_contract")}</Button>}</td>
          </tr>))}</tbody>
      </table></div>
      {term && <TerminateDialog path={`/contracts/${term.id}/terminate`} title={`${t("term_contract")} — ${term.name}`} desc={t("term_contract_desc")} onClose={() => setTerm(null)} onDone={reload} testid="legacy-term" />}
    </div>
  );
}
