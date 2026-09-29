import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FilePlus2, Send } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardTitle, Empty } from "@/components/common";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate, yen } from "@/lib/format";
import EContractForm from "./EContractForm";
import LegacyContracts from "./LegacyContracts";

const TONE = { ACTIVE: "bg-emerald-50 text-emerald-700", ENDED: "bg-slate-100 text-slate-500", CANCELLED: "bg-red-50 text-red-600", PAUSED: "bg-amber-50 text-amber-700" };
export const StatusPill = ({ s, t }) => <span className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${TONE[s] || "bg-sky-50 text-sky-700"}`} data-testid="ec-status">{t(`ec_${s}`)}</span>;
const GROUPS = [["ec_g_confirm", ["IMPORTANT_INFO_SENT"]], ["ec_g_sign", ["CONTRACT_SENT"]], ["ec_g_progress", ["IMPORTANT_INFO_CONFIRMED", "FIRST_PARTY_SIGNED", "BOTH_SIGNED"]],
  ["ec_g_active", ["ACTIVE", "PAUSED"]], ["ec_g_ended", ["ENDED", "CANCELLED"]]];
const mark = (v) => (v ? `✓ ${fmtDate(v)}` : "—");

function Rows({ rows, saas, t, nav, onProof }) {
  return (
    <div className="overflow-x-auto"><table className="data-table w-full text-sm">
      <thead><tr>{["ec_number", saas ? "tenants" : "client", "ec_service", "status", "ec_important", "ec_recipient_sign", "ec_issuer_sign", "ec_start", "ec_end", "ec_fee", "ec_next_invoice", ...(saas ? ["payment_status"] : []), ""].map((h) => <th key={h}>{h && t(saas && h === "ec_recipient_sign" ? "ec_consultant_sign" : saas && h === "ec_issuer_sign" ? "ec_finora_sign" : h)}</th>)}</tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={r.id} onClick={() => nav(`/econtracts/${r.id}`)} className="cursor-pointer hover:bg-slate-50" data-testid={`ec-row-${r.id}`}>
          <td className="font-num text-xs">{r.number} <span className="text-slate-400">v{r.version}</span></td>
          <td>{saas ? <>{r.tenant_name}<div className="text-[11px] text-slate-400">{r.owner_name}</div></> : r.client_name}</td>
          <td>{r.terms.service_name}</td><td><StatusPill s={r.status} t={t} /></td>
          <td className="text-xs">{mark(r.confirmed_at)}</td><td className="text-xs">{mark(r.recipient_signed_at)}</td><td className="text-xs">{mark(r.issuer_signed_at)}</td>
          <td className="font-num text-xs">{fmtDate(r.terms.start_date)}</td><td className="font-num text-xs">{fmtDate(r.end_date || r.terms.end_date)}</td>
          <td className="font-num">{saas ? yen(r.fee_amount) : yen(r.terms.fee)}<div className="text-[10px] text-slate-400">{t(`cyc_${r.terms.fee_type}`)}</div></td>
          <td className="font-num text-xs">{fmtDate(r.next_invoice_date || (saas ? r.renewal_date : null))}</td>
          {saas && <td className="text-xs">{r.payment_status || "—"}</td>}
          <td>{onProof && ["ACTIVE", "ENDED"].includes(r.status) && <Button size="sm" variant="outline" title={t("ec_proof_hint")} onClick={(e) => { e.stopPropagation(); onProof(r); }} data-testid={`ec-proof-${r.id}`}><Send className="mr-1 h-3.5 w-3.5" />{t("ec_send_proof")}</Button>}</td>
        </tr>))}</tbody>
    </table></div>
  );
}

export default function EContractPanel({ type = "CONSULTING", clientId, mine, allowCreate, grouped, title }) {
  const { t, user } = useApp();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const saas = type === "FINORA_SAAS";
  const { data, reload } = useApi(`/econtracts?type=${type}${clientId ? `&client_id=${clientId}` : ""}${mine ? "&mine=true" : ""}`);
  const rows = data || [];
  const onProof = user?.role === "client" ? null : async (r) => {
    try { const { data: res } = await api.post(`/econtracts/${r.id}/send-proof`); toast.success(`${t("ec_proof_sent")}（${res.certificate_number}）`); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const body = !rows.length ? <Empty text={t("no_data")} /> : grouped
    ? GROUPS.map(([g, st]) => { const rs = rows.filter((r) => st.includes(r.status)); return rs.length ? <div key={g} className="mb-5" data-testid={`ec-group-${g}`}><div className="mb-2 text-xs font-semibold text-slate-500">{t(g)} ({rs.length})</div><Rows rows={rs} saas={saas} t={t} nav={nav} onProof={onProof} /></div> : null; })
    : <Rows rows={rows} saas={saas} t={t} nav={nav} onProof={onProof} />;
  return (
    <Card data-testid={`ec-panel-${type}`}>
      <CardTitle right={allowCreate && <Button className="btn-emerald" onClick={() => setOpen(true)} data-testid="ec-new-btn"><FilePlus2 className="mr-1 h-4 w-4" />{t(saas ? "ec_new_saas" : "ec_new")}</Button>}>{title || t(saas ? "ec_finora_contract" : "ec_client_contract")}</CardTitle>
      {body}
      {!saas && <LegacyContracts clientId={clientId} />}
      {open && <EContractForm type={type} clientId={clientId} onClose={() => setOpen(false)} onDone={(id) => nav(`/econtracts/${id}`)} />}
    </Card>
  );
}
