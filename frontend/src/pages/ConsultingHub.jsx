import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { REQ_CATS, REQ_STATUS } from "@/config/entities";
import { Card, Empty, PageHeader } from "@/components/common";
import { useScopeLabel } from "@/lib/useDashboard";
import EntityManager from "@/components/EntityManager";
import MeetingsPanel, { NewMeeting } from "@/components/MeetingsPanel";
import CommentThread from "@/components/CommentThread";

const inp = "h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm";
const st = (s) => (s === "new" ? "new_status" : s);

function NewRequest({ onDone }) {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ category: "rc_portfolio", title: "", content: "", preferred_at: "", notes: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async () => {
    try { await api.post("/requests", { ...f, preferred_at: f.preferred_at || null }); toast.success(t("saved")); setOpen(false); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <>
      <Button className="btn-emerald" onClick={() => setOpen(true)} data-testid="new-request-btn"><Plus className="mr-1 h-4 w-4" />{t("new_request")}</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg" data-testid="new-request-dialog">
          <DialogHeader><DialogTitle className="font-display">{t("new_request")}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <select className={inp} value={f.category} onChange={set("category")} data-testid="request-category">{REQ_CATS.map((c) => <option key={c} value={c}>{t(c)}</option>)}</select>
            <input className={inp} placeholder={t("title")} value={f.title} onChange={set("title")} data-testid="request-title" />
            <textarea rows={4} className="w-full rounded-lg border border-slate-200 p-3 text-sm" placeholder={t("content")} value={f.content} onChange={set("content")} data-testid="request-content" />
            <label className="block text-xs text-slate-600">{t("preferred_at")}<input type="datetime-local" className={`${inp} mt-1`} value={f.preferred_at} onChange={set("preferred_at")} data-testid="request-preferred" /></label>
            <input className={inp} placeholder={t("notes")} value={f.notes} onChange={set("notes")} data-testid="request-notes" />
          </div>
          <DialogFooter><Button className="btn-emerald" onClick={submit} data-testid="request-submit">{t("send")}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function RequestCard({ r, onDone }) {
  const { t, isClient, clientName } = useApp();
  const [m, setM] = useState({ status: r.status, answer: r.answer || "", meeting_at: "" });
  const [book, setBook] = useState(false);
  const save = async () => {
    try { await api.put(`/requests/${r.id}/manage`, { status: m.status, answer: m.answer || null, meeting_at: m.meeting_at || null }); toast.success(t("saved")); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4" data-testid={`request-${r.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-[#071A2B]">{r.title}</span>
        <span className="rounded bg-slate-100 px-1.5 text-[11px]">{t(r.category)}</span>
        <span className="rounded-full bg-emerald-50 px-2 text-[11px] font-semibold text-[#00A878]" data-testid={`request-status-${r.id}`}>{t(st(r.status))}</span>
        <span className="ml-auto text-[11px] text-slate-400">{clientName(r.client_id)} · <span className="font-num">{fmtDateTime(r.created_at)}</span></span>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{r.content}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {r.video_meeting_at && <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700" data-testid={`request-video-at-${r.id}`}><Video className="h-3.5 w-3.5" />{t("mt_title_panel")}: {new Date(r.video_meeting_at).toLocaleString("ja-JP", { dateStyle: "medium", timeStyle: "short" })}</span>}
        {!isClient && !r.video_meeting_at && <Button size="sm" variant="outline" onClick={() => setBook(true)} data-testid={`request-book-video-${r.id}`}><Video className="mr-1 h-4 w-4" />{t("mt_new")}</Button>}
      </div>
      {book && <NewMeeting preset={{ client_id: r.client_id, title: r.title, request_id: r.id }} onClose={() => setBook(false)} onDone={onDone} />}
      {r.answer && <div className="mt-2 rounded-lg bg-slate-50 p-2.5 text-sm"><b className="text-xs text-slate-500">{t("answer")}:</b> {r.answer}</div>}
      {!isClient && (
        <div className="mt-3 grid gap-2 md:grid-cols-[160px_1fr_170px_auto]">
          <select className={inp} value={m.status} onChange={(e) => setM({ ...m, status: e.target.value })} data-testid={`request-manage-status-${r.id}`}>{REQ_STATUS.map((s) => <option key={s} value={s}>{t(st(s))}</option>)}</select>
          <input className={inp} placeholder={t("answer")} value={m.answer} onChange={(e) => setM({ ...m, answer: e.target.value })} data-testid={`request-answer-${r.id}`} />
          <input type="date" className={inp} value={m.meeting_at} onChange={(e) => setM({ ...m, meeting_at: e.target.value })} title={t("meeting_at")} data-testid={`request-meeting-${r.id}`} />
          <Button className="btn-emerald h-10" onClick={save} data-testid={`request-save-${r.id}`}>{t("save")}</Button>
        </div>
      )}
      <div className="mt-3 border-t pt-3"><CommentThread clientId={r.client_id} targetType="request" targetId={r.id} targetLabel={r.title} /></div>
    </div>
  );
}

function CorrectionCard({ c, onDone }) {
  const { t, isClient, clientName } = useApp();
  const [note, setNote] = useState("");
  const act = async (path, body) => { try { await api.put(`/corrections/${c.id}/${path}`, body); toast.success(t("saved")); onDone(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4" data-testid={`correction-${c.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-[#071A2B]">{t(c.target_entity === "portfolio" ? "portfolio_target" : c.target_entity)}{c.target_label && ` — ${c.target_label}`}</span>
        <span className={`rounded-full px-2 text-[11px] font-semibold ${c.status === "open" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-[#00A878]"}`} data-testid={`correction-status-${c.id}`}>{t(c.status)}</span>
        <span className="ml-auto text-[11px] text-slate-400">{clientName(c.client_id)} · {c.created_by_name} · {t("due_date")} {fmtDate(c.due_date)}</span>
      </div>
      <div className="mt-2 grid gap-1 text-sm"><div><b className="text-xs text-slate-500">{t("reason")}:</b> {c.reason}</div><div><b className="text-xs text-slate-500">{t("requested_change")}:</b> {c.requested_change}</div>{c.comment && <div className="text-slate-600">{c.comment}</div>}{c.resolution_note && <div className="text-[#00A878]">{t("resolution_note")}: {c.resolution_note}</div>}</div>
      {isClient && c.status === "open" && (
        <div className="mt-3 flex gap-2"><input className={inp} placeholder={t("resolution_note")} value={note} onChange={(e) => setNote(e.target.value)} data-testid={`correction-note-${c.id}`} />
          <Button className="btn-emerald h-10" onClick={() => act("resolve", { note })} data-testid={`correction-resolve-${c.id}`}>{t("mark_resolved")}</Button></div>
      )}
      {!isClient && c.status === "resolved" && <Button variant="outline" size="sm" className="mt-3" onClick={() => act("close")} data-testid={`correction-close-${c.id}`}>{t("close")}</Button>}
      <div className="mt-3 border-t pt-3"><CommentThread clientId={c.client_id} targetType="correction" targetId={c.id} targetLabel={c.target_label} /></div>
    </div>
  );
}

export function ConsultingPanels({ clientId }) {
  const { t, isClient } = useApp();
  const [sp] = useSearchParams();
  const q = clientId ? `?client_id=${clientId}` : "";
  const reqs = useApi(`/requests${q}`, [clientId]);
  const corr = useApi(`/corrections${q}`, [clientId]);
  return (
    <>
    <MeetingsPanel clientId={clientId} />
    <Tabs defaultValue={sp.get("tab") || "requests"}>
      <TabsList className="h-auto flex-wrap bg-white/70 p-1">
        {["consulting_requests", "corrections", "consulting_records"].map((k, i) => <TabsTrigger key={k} value={["requests", "corrections", "records"][i]} data-testid={`consulting-tab-${k}`} className="data-[state=active]:bg-[#071A2B] data-[state=active]:text-white">{t(k)}</TabsTrigger>)}
      </TabsList>
      <TabsContent value="requests" className="mt-4 space-y-3">
        {isClient && <NewRequest onDone={reqs.reload} />}
        {!(reqs.data || []).length ? <Card><Empty text={t("no_data")} /></Card> : reqs.data.map((r) => <RequestCard key={r.id} r={r} onDone={reqs.reload} />)}
      </TabsContent>
      <TabsContent value="corrections" className="mt-4 space-y-3">
        {!(corr.data || []).length ? <Card><Empty text={t("no_data")} /></Card> : corr.data.map((c) => <CorrectionCard key={c.id} c={c} onDone={corr.reload} />)}
      </TabsContent>
      <TabsContent value="records" className="mt-4"><EntityManager entity="consulting" clientId={clientId} /></TabsContent>
    </Tabs>
    </>
  );
}

export default function ConsultingHub() {
  const { t, scopeClient } = useApp();
  const scope = useScopeLabel();
  return (
    <div data-testid="consulting-page">
      <PageHeader eyebrow={`Consulting · ${scope}`} title={t("consulting")} />
      <ConsultingPanels key={scopeClient} clientId={scopeClient} />
    </div>
  );
}
