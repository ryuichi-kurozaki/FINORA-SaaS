import { useEffect, useState } from "react";
import { toast } from "sonner";
import { RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { Card, CardTitle, Spinner } from "@/components/common";

const KINDS = ["invite", "econtract", "renewal", "termination", "meeting", "invoice", "refund", "inquiry", "system", "other"];
const STATUSES = ["delivered", "queued", "deferred", "bounced", "failed", "logged"];
const TONE = { delivered: "bg-emerald-50 text-emerald-700", queued: "bg-sky-50 text-sky-700", deferred: "bg-amber-50 text-amber-700", bounced: "bg-red-50 text-red-700", failed: "bg-red-100 text-red-800", logged: "bg-slate-100 text-slate-600" };
const PAGE = 50;
const sel = "h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm";

function StatusChips({ counts, status, setStatus, t }) {
  const all = Object.values(counts || {}).reduce((a, b) => a + b, 0);
  const chip = (k, label, n) => (
    <button key={k || "all"} onClick={() => setStatus(k)} data-testid={`email-log-chip-${k || "all"}`}
      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${status === k ? "bg-[#071A2B] text-white" : "bg-white text-slate-600 hover:bg-slate-100"}`}>
      {label} <span className="font-num">{n}</span></button>);
  return <div className="flex flex-wrap gap-2">{chip("", t("el_all"), all)}{STATUSES.map((s) => chip(s, t(`el_st_${s}`), counts?.[s] || 0))}</div>;
}

function LogTable({ items, t }) {
  return (
    <div className="overflow-x-auto"><table className="data-table w-full min-w-[860px] text-sm" data-testid="email-log-table">
      <thead><tr>{["el_at", "el_to", "el_subject", "el_kind", "el_status"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
      <tbody>{items.length === 0 && <tr><td colSpan={5} className="text-center text-xs text-slate-400" data-testid="email-log-empty">{t("el_empty")}</td></tr>}
        {items.map((r, i) => (
          <tr key={r.id || r.message_id || i} data-testid={`email-log-row-${r.id || i}`}>
            <td className="whitespace-nowrap font-num text-xs">{fmtDateTime(r.at)}</td>
            <td className="text-xs">{r.to}</td>
            <td className="max-w-[320px] truncate" title={r.subject}>{r.subject}</td>
            <td className="text-xs">{t(`el_kind_${r.kind || "other"}`)}</td>
            <td><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${TONE[r.status] || TONE.logged}`} data-testid={`email-log-status-${r.id || i}`}>{t(`el_st_${r.status || "logged"}`)}</span>
              {r.detail && <div className="mt-1 max-w-[260px] truncate text-[11px] text-slate-400" title={r.detail}>{r.detail}</div>}</td>
          </tr>))}</tbody>
    </table></div>
  );
}

export default function EmailLogPanel() {
  const { t } = useApp();
  const [f, setF] = useState({ q: "", kind: "", status: "" });
  const [q, setQ] = useState("");
  const [skip, setSkip] = useState(0);
  const [data, setData] = useState(null);
  const load = () => api.get("/platform/email-log", { params: { ...f, skip, limit: PAGE } }).then((r) => setData(r.data)).catch((e) => toast.error(errMsg(e)));
  useEffect(() => { load(); }, [f, skip]); // eslint-disable-line react-hooks/exhaustive-deps
  const upd = (k, v) => { setSkip(0); setF((p) => ({ ...p, [k]: v })); };
  const sync = async () => {
    try { const { data: r } = await api.post("/platform/email-log/sync"); toast.success(t("el_synced").replace("{n}", r.updated)); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card data-testid="email-log-panel">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div><CardTitle>{t("email_log")}</CardTitle><p className="text-xs text-slate-500">{t("el_note")}</p></div>
        <Button variant="outline" size="sm" onClick={sync} data-testid="email-log-sync-btn"><RefreshCw className="mr-1 h-4 w-4" />{t("el_sync")}</Button>
      </div>
      <form className="mb-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); upd("q", q); }}>
        <div className="relative min-w-[240px] flex-1"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("el_search")} className={`${sel} w-full pl-9`} data-testid="email-log-search" /></div>
        <select value={f.kind} onChange={(e) => upd("kind", e.target.value)} className={sel} data-testid="email-log-kind">
          <option value="">{t("el_all_kinds")}</option>{KINDS.map((k) => <option key={k} value={k}>{t(`el_kind_${k}`)}</option>)}</select>
        <Button type="submit" className="btn-emerald" data-testid="email-log-search-btn">{t("el_search_btn")}</Button>
      </form>
      {!data ? <Spinner /> : <>
        <div className="mb-3"><StatusChips counts={data.counts} status={f.status} setStatus={(s) => upd("status", s)} t={t} /></div>
        <LogTable items={data.items} t={t} />
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span data-testid="email-log-total">{t("el_total").replace("{n}", data.total)}{data.synced_at && ` · ${t("el_synced_at")} ${fmtDateTime(data.synced_at)}`}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE))} data-testid="email-log-prev">{t("el_prev")}</Button>
            <Button size="sm" variant="outline" disabled={skip + PAGE >= data.total} onClick={() => setSkip(skip + PAGE)} data-testid="email-log-next">{t("el_next")}</Button>
          </div>
        </div></>}
    </Card>
  );
}
