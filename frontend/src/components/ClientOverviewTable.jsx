import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, MailPlus, Search } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate, yen } from "@/lib/format";
import { Card, CardTitle, Spinner } from "@/components/common";
import { ST } from "@/pages/Billing";

const HC = { ok: "bg-emerald-50 text-emerald-700", review: "bg-amber-50 text-amber-700", attention: "bg-red-50 text-red-700" };

function InviteDialog({ client, onClose, onDone }) {
  const { t } = useApp();
  const [email, setEmail] = useState("");
  const [link, setLink] = useState("");
  const send = async () => {
    try { const { data } = await api.post("/invitations", { client_id: client.id, email }); setLink(`${window.location.origin}${data.path}`); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={!!client} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>{t("invite_client")} · {client?.name}</DialogTitle></DialogHeader>
        {!link ? (
          <label className="text-xs text-slate-600">{t("email")}<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm" data-testid="invite-email" /></label>
        ) : (
          <div className="space-y-2" data-testid="invite-link-box">
            <div className="text-xs text-slate-500">{t("invite_link")}</div>
            <div className="flex gap-2"><input readOnly value={link} className="h-10 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 font-num text-xs" data-testid="invite-link" />
              <Button variant="outline" onClick={() => { navigator.clipboard?.writeText(link); toast.success(t("copied")); }} data-testid="invite-copy"><Copy className="h-4 w-4" /></Button></div>
            <p className="text-[11px] text-[#8a6d12]">{t("invite_mock_note")}</p>
          </div>
        )}
        {!link && <DialogFooter><Button className="btn-emerald" onClick={send} disabled={!email.includes("@")} data-testid="invite-send">{t("invite")}</Button></DialogFooter>}
      </DialogContent>
    </Dialog>
  );
}

export function InvitationsList({ clientId, k }) {
  const { t } = useApp();
  const { data, reload } = useApi(`/invitations${clientId ? `?client_id=${clientId}` : ""}`, [clientId, k]);
  const cancel = async (id) => { try { await api.post(`/invitations/${id}/cancel`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  if (!data?.length) return null;
  return (
    <Card><CardTitle>{t("invitations")}</CardTitle>
      <div className="overflow-x-auto"><table className="data-table w-full min-w-[600px] text-sm" data-testid="invitation-table">
        <thead><tr>{["email", "invited_by", "date", "expiry_date", "status", ""].map((h) => <th key={h}>{h && t(h)}</th>)}</tr></thead>
        <tbody>{data.map((i) => (
          <tr key={i.id}><td>{i.email}</td><td>{i.invited_by_name}</td><td className="font-num">{fmtDate(i.created_at)}</td><td className="font-num">{fmtDate(i.expires_at)}</td>
            <td><span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs">{t(i.status)}</span></td>
            <td>{i.status === "PENDING" && <button className="text-xs text-red-600" onClick={() => cancel(i.id)} data-testid={`invitation-cancel-${i.id}`}>{t("CANCELLED")}</button>}</td></tr>
        ))}</tbody>
      </table></div>
    </Card>
  );
}

export default function ClientOverviewTable() {
  const { t } = useApp();
  const { data, loading } = useApi("/clients/overview");
  const [q, setQ] = useState("");
  const [flt, setFlt] = useState("");
  const [inv, setInv] = useState(null);
  const [k, setK] = useState(0);
  const rows = useMemo(() => (data || []).filter((r) => (!q || r.name?.toLowerCase().includes(q.toLowerCase())) &&
    (!flt || (flt === "unpaid" ? r.unpaid > 0 : flt === "attention" ? r.health !== "ok" : r.contract_status === flt))), [data, q, flt]);
  return (
    <div className="space-y-6">
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <CardTitle>{t("client_list")}</CardTitle>
          <div className="ml-auto flex items-center gap-2">
            <div className="relative"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")} className="h-9 rounded-lg border border-slate-200 pl-8 pr-3 text-sm" data-testid="client-overview-search" /></div>
            <select value={flt} onChange={(e) => setFlt(e.target.value)} className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-sm" data-testid="client-overview-filter">
              <option value="">—</option><option value="ACTIVE">{t("ACTIVE")}</option><option value="unpaid">{t("unpaid_badge")}</option><option value="attention">{t("health_review")}</option>
            </select>
          </div>
        </div>
        {loading ? <Spinner /> : (
          <div className="overflow-x-auto"><table className="data-table w-full min-w-[1100px] text-sm" data-testid="client-overview-table">
            <thead><tr>{["name", "client_type", "contract_status", "consultant_id", "last_login", "last_update", "next_meeting", "open_requests", "unpaid", "data_health", "actions"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id} data-testid={`client-overview-row-${r.id}`}>
                <td><Link to={`/clients/${r.id}`} className="font-medium text-[#071A2B] hover:text-[#00A878]">{r.name}</Link></td>
                <td>{t(r.client_type)}</td>
                <td>{r.contract_status ? <span className={`rounded-md px-2 py-0.5 text-xs ${r.contract_status === "ACTIVE" ? ST.PAID : ST.DRAFT}`}>{t(r.contract_status)}</span> : "—"}</td>
                <td>{r.consultant || "—"}</td><td className="font-num text-xs">{fmtDate(r.last_login)}</td><td className="font-num text-xs">{fmtDate(r.last_update)}</td>
                <td className="font-num text-xs">{r.next_meeting || "—"}</td><td className="text-center">{r.open_requests || "—"}</td>
                <td>{r.unpaid > 0 ? <span className={`font-num text-xs font-semibold ${r.overdue ? "text-red-600" : "text-[#8a6d12]"}`}>{yen(r.unpaid)}</span> : "—"}</td>
                <td><span className={`rounded-md px-2 py-0.5 text-xs ${HC[r.health]}`}>{t(`health_${r.health}`)} {r.health_score}</span></td>
                <td><button className="icon-btn text-[#00A878]" onClick={() => setInv(r)} title={t("invite")} data-testid={`client-invite-${r.id}`}><MailPlus className="h-4 w-4" /></button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      <InvitationsList k={k} />
      <InviteDialog key={inv?.id} client={inv} onClose={() => setInv(null)} onDone={() => setK(k + 1)} />
    </div>
  );
}
