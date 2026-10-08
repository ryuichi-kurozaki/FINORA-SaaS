import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, CardTitle, Empty } from "@/components/common";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";

const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40";
const fmt = (s) => new Date(s).toLocaleString("ja-JP", { dateStyle: "medium", timeStyle: "short" });
const durLabel = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const joinable = (m) => ["SCHEDULED", "LIVE"].includes(m.status);

export function NewMeeting({ clientId, preset, instant, onClose, onDone }) {
  const { t, clients } = useApp();
  const nav = useNavigate();
  const [f, setF] = useState({ client_id: clientId || preset?.client_id || "", title: preset?.title || "", when: "", duration_min: 60 });
  const save = async () => {
    try {
      const { data } = await api.post("/meetings", { client_id: f.client_id, title: f.title || t("mt_title_panel"), scheduled_at: instant ? new Date().toISOString() : new Date(f.when).toISOString(), duration_min: Number(f.duration_min), request_id: preset?.request_id || null });
      window.dispatchEvent(new Event("finora:meetings")); onDone(); onClose();
      if (instant && data?.id) { nav(`/meetings/${data.id}`); } else { toast.success(t("mt_scheduled")); }
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md" data-testid="meeting-new-dialog">
        <DialogHeader><DialogTitle className="font-display">{instant ? t("mt_start_now") : t("mt_new")}</DialogTitle></DialogHeader>
        {!clientId && !preset?.client_id && <label className="block text-xs">{t("client")}<select className={inp} value={f.client_id} onChange={(e) => setF({ ...f, client_id: e.target.value })} data-testid="meeting-client"><option value="">—</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.corporate_name || c.name}</option>)}</select></label>}
        <label className="block text-xs">{t("mt_title")}<input className={inp} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} data-testid="meeting-title" /></label>
        {!instant && <label className="block text-xs">{t("mt_when")}<input type="datetime-local" className={inp} value={f.when} onChange={(e) => setF({ ...f, when: e.target.value })} data-testid="meeting-when" /></label>}
        <label className="block text-xs">{t("mt_duration")}<select className={inp} value={f.duration_min} onChange={(e) => setF({ ...f, duration_min: e.target.value })} data-testid="meeting-duration">{[30, 60, 90, 120].map((d) => <option key={d} value={d}>{d}</option>)}</select></label>
        <DialogFooter><Button className="btn-emerald" disabled={!f.client_id || (!instant && !f.when)} onClick={save} data-testid="meeting-save">{instant ? t("mt_start_now") : t("mt_schedule")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MinutesBox({ m, staff, reload }) {
  const { t, lang } = useApp();
  const LANGS = ["ja", "en", "pt"];
  const LABEL = { ja: "日本語", en: "English", pt: "Português" };
  const pick = (map) => map && (map[lang] || map.ja || map.en || map.pt) || "";
  const draft = m.minutes_i18n || (m.minutes ? { ja: m.minutes } : {});
  const appr = m.minutes_approved_i18n || (m.minutes_approved ? { ja: m.minutes_approved } : {});
  const [elang, setELang] = useState(lang);
  const [text, setText] = useState(draft[lang] || pick(draft));
  const [tr, setTr] = useState(null);
  useEffect(() => { setText((m.minutes_i18n || (m.minutes ? { ja: m.minutes } : {}))[elang] || ""); }, [elang]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (fn) => { try { await fn(); toast.success(t("saved")); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const box = "mt-3 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-xs leading-relaxed text-slate-700";
  if (!staff) return pick(appr) ? <pre className={box} data-testid={`meeting-minutes-text-${m.id}`}>{pick(appr)}</pre> : null;
  if (!["DRAFT", "APPROVED"].includes(m.minutes_status)) return pick(draft) ? <pre className={box} data-testid={`meeting-minutes-text-${m.id}`}>{pick(draft)}</pre> : null;
  const saved = draft[elang] || "";
  return (
    <div className="mt-3 space-y-2" data-testid={`meeting-minutes-editor-${m.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-xs font-semibold text-slate-500">{t(`mt_minutes_${m.minutes_status}`)}{m.minutes_approved_at && ` · ${t("mt_last_approved")} ${fmt(m.minutes_approved_at)}`}</div>
        <div className="ml-auto flex gap-1" data-testid={`meeting-minutes-langs-${m.id}`}>
          {LANGS.map((l) => <button key={l} onClick={() => setELang(l)} className={`rounded-md px-2 py-0.5 text-xs font-semibold ${elang === l ? "bg-[#071A2B] text-white" : "bg-slate-100 text-slate-600"}`} data-testid={`meeting-minutes-lang-${l}-${m.id}`}>{LABEL[l]}</button>)}
        </div>
      </div>
      <textarea rows={12} value={text} onChange={(e) => setText(e.target.value)} className="w-full rounded-lg border border-slate-200 p-3 text-xs leading-relaxed" data-testid={`meeting-minutes-input-${m.id}`} />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={!text.trim() || text === saved} onClick={() => run(() => api.put(`/meetings/${m.id}/minutes`, { text, lang: elang }))} data-testid={`meeting-minutes-save-${m.id}`}>{t("save")}</Button>
        <Button size="sm" className="btn-emerald" disabled={m.minutes_status !== "DRAFT" || text !== saved} onClick={() => run(() => api.post(`/meetings/${m.id}/minutes/approve`))} data-testid={`meeting-minutes-approve-${m.id}`}>{t("mt_approve")}</Button>
        <Button size="sm" variant="ghost" onClick={async () => setTr(tr === null ? (await api.get(`/meetings/${m.id}/transcript`)).data.transcript : null)} data-testid={`meeting-transcript-btn-${m.id}`}>{t("mt_transcript")}</Button>
      </div>
      {tr !== null && <pre className={box} data-testid={`meeting-transcript-${m.id}`}>{tr || "—"}</pre>}
    </div>
  );
}

function Row({ m, staff, reload }) {
  const { t } = useApp();
  const nav = useNavigate();
  const [video, setVideo] = useState(null);
  const [minutes, setMinutes] = useState(false);
  const play = async () => { try { const { data } = await api.get(`/meetings/${m.id}/recording-url`); setVideo(`${process.env.REACT_APP_BACKEND_URL}${data.url}`); } catch (e) { toast.error(errMsg(e)); } };
  const cancel = async () => { if (!window.confirm(t("mt_cancel_confirm"))) return; try { await api.post(`/meetings/${m.id}/cancel`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="rounded-xl border border-slate-100 p-3" data-testid={`meeting-row-${m.id}`}>
      <div className="flex flex-wrap items-center gap-3">
        <Video className="h-4 w-4 text-[#00A878]" />
        <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold text-[#071A2B]">{m.title}</div>
          <div className="text-xs text-slate-500">{fmt(m.scheduled_at)} · {m.duration_min}{t("mt_min")} · {m.client_name} · <span data-testid={`meeting-status-${m.id}`}>{t(`mt_st_${m.status}`)}</span>{m.call_duration_sec ? <span data-testid={`meeting-calldur-${m.id}`}> · {t("mt_call_duration")} {durLabel(m.call_duration_sec)}</span> : null}</div></div>
        {joinable(m) && <Button size="sm" className="btn-emerald" onClick={() => nav(`/meetings/${m.id}`)} data-testid={`meeting-join-${m.id}`}>{t("mt_join")}</Button>}
        {m.recording && !m.recording_deleted && <Button size="sm" variant="outline" onClick={play} data-testid={`meeting-play-${m.id}`}>{t("mt_play")}</Button>}
        {(staff ? m.minutes_status : m.minutes_approved) && <Button size="sm" variant="outline" onClick={() => setMinutes(!minutes)} data-testid={`meeting-minutes-${m.id}`}>{t(!staff || ["DRAFT", "APPROVED"].includes(m.minutes_status) ? "mt_minutes" : `mt_minutes_${m.minutes_status}`)}</Button>}
        {staff && m.status === "SCHEDULED" && <Button size="sm" variant="outline" className="text-red-600" onClick={cancel} data-testid={`meeting-cancel-${m.id}`}>{t("cancel")}</Button>}
      </div>
      {video && <video src={video} controls className="mt-3 w-full max-w-xl rounded-lg bg-black" data-testid={`meeting-video-${m.id}`} />}
      {minutes && <MinutesBox m={m} staff={staff} reload={reload} />}
    </div>
  );
}

export default function MeetingsPanel({ clientId }) {
  const { t, isClient } = useApp();
  const { data, reload } = useApi(`/meetings${clientId ? `?client_id=${clientId}` : ""}`, [clientId]);
  const [open, setOpen] = useState(false);
  useEffect(() => { window.addEventListener("finora:meetings", reload); return () => window.removeEventListener("finora:meetings", reload); }, [reload]);
  return (
    <Card className="mb-6" data-testid="meetings-panel">
      <CardTitle right={!isClient && <div className="flex gap-2">
        <Button className="btn-emerald" onClick={() => setOpen("instant")} data-testid="meeting-start-now-btn"><Video className="mr-1 h-4 w-4" />{t("mt_start_now")}</Button>
        <Button variant="outline" onClick={() => setOpen("schedule")} data-testid="meeting-new-btn">{t("mt_new")}</Button>
      </div>}>{t("mt_title_panel")}</CardTitle>
      {!data?.length ? <Empty text={t("no_data")} /> : <div className="space-y-2">{data.map((m) => <Row key={m.id} m={m} staff={!isClient} reload={reload} />)}</div>}
      {open && <NewMeeting clientId={clientId} instant={open === "instant"} onClose={() => setOpen(false)} onDone={reload} />}
    </Card>
  );
}
