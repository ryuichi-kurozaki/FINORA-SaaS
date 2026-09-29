import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Copy, FileText, Mail, MailPlus, Search } from "lucide-react";
import { WhatsAppIcon } from "@/components/WhatsAppIcon";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate, yen } from "@/lib/format";
import { Card, CardTitle, Spinner } from "@/components/common";
import { ST } from "@/pages/Billing";
import EContractForm from "@/components/econtract/EContractForm";

const HC = { ok: "bg-emerald-50 text-emerald-700", review: "bg-amber-50 text-amber-700", attention: "bg-red-50 text-red-700" };

function DeliveryBadges({ d, t }) {
  if (!d) return <span className="text-xs text-slate-400">—</span>;
  const cls = { SENT: "bg-emerald-50 text-emerald-700 ring-emerald-200", FAILED: "bg-red-50 text-red-600 ring-red-200", SKIPPED: "bg-slate-50 text-slate-300 ring-slate-200" };
  const ic = { email: <Mail className="h-3.5 w-3.5" />, whatsapp: <WhatsAppIcon className="h-3.5 w-3.5" /> };
  return <span className="flex gap-1.5">{["email", "whatsapp"].map((k) => (
    <span key={k} title={`${k === "email" ? t("email") : "WhatsApp"}: ${t(`dlv_${d[k]}`)}`} className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] ring-1 ${cls[d[k]]}`} data-testid={`delivery-${k}`}>{ic[k]}{d[k] !== "SKIPPED" && t(`dlv_${d[k]}`)}</span>))}</span>;
}

function InviteDialog({ client, mode, onClose, onDone }) {
  const { t } = useApp();
  const { data: rec } = useApi(`/data/clients/${client.id}`, [client.id]);
  const [f, setF] = useState(null);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const wa = mode === "whatsapp";
  const v = f || { email: wa ? "" : rec?.email || "", whatsapp: rec?.whatsapp || "" };
  const send = async () => {
    setBusy(true);
    try { const { data } = await api.post("/invitations", { client_id: client.id, channel: mode, ...v }); setRes({ link: `${window.location.origin}${data.path}`, d: data.delivery }); onDone(); } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };
  const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm";
  const ok = wa ? v.whatsapp.replace(/\D/g, "").length >= 8 : v.email.includes("@");
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md" data-testid="invite-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2">{wa ? <WhatsAppIcon className="h-5 w-5 text-[#25D366]" /> : <MailPlus className="h-5 w-5 text-[#00A878]" />}{t(wa ? "invite_by_whatsapp" : "invite_client")} · {client.name}</DialogTitle></DialogHeader>
        {!res ? (
          <div className="grid gap-3">
            {wa ? <label className="text-xs text-slate-600">{t("client_whatsapp")} *<input value={v.whatsapp} onChange={(e) => setF({ ...v, whatsapp: e.target.value })} placeholder="090-1234-5678 / +55 11 91234-5678" className={inp} data-testid="invite-whatsapp" /></label>
              : <>
                <label className="text-xs text-slate-600">{t("email")} *<input type="email" value={v.email} onChange={(e) => setF({ ...v, email: e.target.value })} className={inp} data-testid="invite-email" /></label>
                <label className="text-xs text-slate-600">{t("client_whatsapp")}<input value={v.whatsapp} onChange={(e) => setF({ ...v, whatsapp: e.target.value })} placeholder="090-1234-5678 / +55 11 91234-5678" className={inp} data-testid="invite-whatsapp" /></label>
              </>}
            <p className="text-[11px] text-slate-500">{t(wa ? "invite_wa_note" : "invite_send_note")}</p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="invite-link-box">
            <DeliveryBadges d={res.d} t={t} />
            <div className="text-xs text-slate-500">{t("invite_link")}</div>
            <div className="flex gap-2"><input readOnly value={res.link} className="h-10 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 font-num text-xs" data-testid="invite-link" />
              <Button variant="outline" onClick={() => { navigator.clipboard?.writeText(res.link); toast.success(t("copied")); }} data-testid="invite-copy"><Copy className="h-4 w-4" /></Button></div>
          </div>
        )}
        {!res && <DialogFooter><Button className={wa ? "bg-[#25D366] text-white hover:bg-[#1ebe5b]" : "btn-emerald"} onClick={send} disabled={busy || !ok} data-testid="invite-send">{t(wa ? "invite_send_wa" : "invite")}</Button></DialogFooter>}
      </DialogContent>
    </Dialog>
  );
}

export function InvitationsList({ clientId, k }) {
  const { t } = useApp();
  const { data, reload } = useApi(`/invitations${clientId ? `?client_id=${clientId}` : ""}`, [clientId, k]);
  const cancel = async (id) => { try { await api.post(`/invitations/${id}/cancel`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const resend = async (id) => { try { await api.post(`/invitations/${id}/resend`); toast.success(t("invite_resent")); reload(); } catch (e) { toast.error(errMsg(e)); } };
  if (!data?.length) return null;
  return (
    <Card><CardTitle>{t("invitations")}</CardTitle>
      <div className="overflow-x-auto"><table className="data-table w-full min-w-[760px] text-sm" data-testid="invitation-table">
        <thead><tr>{["email", "client_whatsapp", "invite_delivery", "invited_by", "date", "expiry_date", "status", ""].map((h) => <th key={h}>{h && t(h)}</th>)}</tr></thead>
        <tbody>{data.map((i) => (
          <tr key={i.id}><td>{i.email || "—"}</td><td className="font-num text-xs">{i.whatsapp_masked || "—"}</td><td><DeliveryBadges d={i.delivery} t={t} /></td>
            <td>{i.invited_by_name}</td><td className="font-num">{fmtDate(i.created_at)}</td><td className="font-num">{fmtDate(i.expires_at)}</td>
            <td><span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs">{t(i.status)}</span>
              {i.reminders_sent > 0 && <div className="mt-1 text-[10px] text-slate-500" data-testid={`invitation-reminded-${i.id}`}>{t("invite_reminded")} {i.reminders_sent}{t("invite_times")}</div>}</td>
            <td className="whitespace-nowrap">{["PENDING", "EXPIRED"].includes(i.status) && <button className="mr-3 text-xs text-[#00A878]" onClick={() => resend(i.id)} data-testid={`invitation-resend-${i.id}`}>{t("invite_resend")}</button>}
              {i.status === "PENDING" && <button className="text-xs text-red-600" onClick={() => cancel(i.id)} data-testid={`invitation-cancel-${i.id}`}>{t("CANCELLED")}</button>}</td></tr>
        ))}</tbody>
      </table></div>
    </Card>
  );
}

export default function ClientOverviewTable() {
  const { t } = useApp();
  const nav = useNavigate();
  const { data, loading } = useApi("/clients/overview");
  const [q, setQ] = useState("");
  const [flt, setFlt] = useState("");
  const [inv, setInv] = useState(null);
  const [ec, setEc] = useState(null);
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
                <td className="whitespace-nowrap"><button className="icon-btn text-[#071A2B]" onClick={() => setEc(r)} title={t("ec_new")} data-testid={`client-new-contract-${r.id}`}><FileText className="h-4 w-4" /></button>
                  <button className="icon-btn text-[#00A878]" onClick={() => setInv({ c: r, mode: "email" })} title={t("invite_client")} data-testid={`client-invite-${r.id}`}><MailPlus className="h-4 w-4" /></button>
                  <button className="icon-btn !text-[#25D366]" onClick={() => setInv({ c: r, mode: "whatsapp" })} title={t("invite_by_whatsapp")} data-testid={`client-invite-wa-${r.id}`}><WhatsAppIcon /></button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      <InvitationsList k={k} />
      {inv && <InviteDialog key={inv.c.id + inv.mode} client={inv.c} mode={inv.mode} onClose={() => setInv(null)} onDone={() => setK(k + 1)} />}
      {ec && <EContractForm type="CONSULTING" clientId={ec.id} onClose={() => setEc(null)} onDone={(id) => nav(`/econtracts/${id}`)} />}
    </div>
  );
}
