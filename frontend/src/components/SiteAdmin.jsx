import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ExternalLink, ImagePlus, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, Spinner } from "@/components/common";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { clearSiteCache, imgSrc } from "@/lib/useSite";

const LANGS3 = ["ja", "en", "pt"];
const inp = "mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm";
const LOC_FIELDS = [["company_name"], ["representative"], ["established"], ["capital"], ["address"], ["business", true], ["employees"], ["phone"], ["email"],
  ["message_title"], ["message_body", true], ["message_signature"], ["access_note"]];
const PLAIN_FIELDS = ["map_url", "social_x", "social_facebook", "social_linkedin", "social_instagram", "social_youtube"];

function LocInput({ label, value, onChange, multi, testid }) {
  const v = value || {};
  return (
    <div className="rounded-xl border border-slate-100 p-3" data-testid={testid}>
      <div className="mb-1 text-xs font-semibold text-slate-600">{label}</div>
      <div className="grid gap-2 md:grid-cols-3">{LANGS3.map((l) => (
        <label key={l} className="text-[10px] uppercase text-slate-400">{l}{l === "ja" && " *"}
          {multi ? <textarea rows={4} value={v[l] || ""} onChange={(e) => onChange({ ...v, [l]: e.target.value })} className={inp} data-testid={`${testid}-${l}`} />
            : <input value={v[l] || ""} onChange={(e) => onChange({ ...v, [l]: e.target.value })} className={inp} data-testid={`${testid}-${l}`} />}</label>))}</div>
    </div>
  );
}

function ImageField({ value, onChange, testid }) {
  const { t } = useApp();
  const ref = useRef(null);
  const up = async (f) => {
    const fd = new FormData(); fd.append("file", f);
    try { const { data } = await api.post("/platform/site/upload", fd); onChange(data.url); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="flex items-center gap-3" data-testid={testid}>
      {value ? <img src={imgSrc(value)} alt="" className="h-16 w-24 rounded-lg object-cover" /> : <div className="h-16 w-24 rounded-lg bg-slate-100" />}
      <input ref={ref} type="file" accept="image/*" hidden onChange={(e) => e.target.files[0] && up(e.target.files[0])} data-testid={`${testid}-file`} />
      <Button type="button" variant="outline" size="sm" onClick={() => ref.current.click()}><ImagePlus className="mr-1 h-4 w-4" />{t("sa_upload")}</Button>
      {value && <button type="button" className="text-xs text-red-600" onClick={() => onChange("")}>{t("delete")}</button>}
    </div>
  );
}

function SettingsForm({ initial, onSaved }) {
  const { t } = useApp();
  const [d, setD] = useState(initial);
  const save = async () => { try { await api.put("/platform/site/settings", { data: d }); clearSiteCache(); toast.success(t("saved")); onSaved(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Card>
      <div className="space-y-3">
        {LOC_FIELDS.map(([k, multi]) => <LocInput key={k} label={t(`co_${k}`)} value={d[k]} multi={multi} onChange={(v) => setD({ ...d, [k]: v })} testid={`sa-${k}`} />)}
        <div className="rounded-xl border border-slate-100 p-3"><div className="mb-2 text-xs font-semibold text-slate-600">{t("sa_message_image")}</div><ImageField value={d.message_image} onChange={(v) => setD({ ...d, message_image: v })} testid="sa-message_image" /></div>
        <div className="grid gap-3 rounded-xl border border-slate-100 p-3 md:grid-cols-2">{PLAIN_FIELDS.map((k) => (
          <label key={k} className="text-xs font-semibold text-slate-600">{t(`sa_${k}`)}<input value={d[k] || ""} onChange={(e) => setD({ ...d, [k]: e.target.value })} placeholder="https://" className={inp} data-testid={`sa-${k}`} /></label>))}</div>
      </div>
      <Button className="btn-emerald mt-4" onClick={save} data-testid="sa-settings-save">{t("save")}</Button>
    </Card>
  );
}

function ItemDialog({ kind, item, onClose, onDone }) {
  const { t } = useApp();
  const [f, setF] = useState(item || { kind, title: {}, body: {}, date: kind === "news" ? new Date().toISOString().slice(0, 10) : "", category: kind === "news" ? "notice" : null, image: "", order: 0, published: true });
  const save = async () => {
    try { item ? await api.put(`/platform/site/items/${item.id}`, f) : await api.post("/platform/site/items", f); clearSiteCache(); toast.success(t("saved")); onDone(); onClose(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto" data-testid="sa-item-dialog">
        <DialogHeader><DialogTitle>{t(`sa_${kind}`)}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <LocInput label={t(kind === "faq" ? "sa_question" : "sa_title")} value={f.title} onChange={(v) => setF({ ...f, title: v })} testid="sa-item-title" />
          <LocInput label={t(kind === "faq" ? "sa_answer" : "sa_body")} value={f.body} multi onChange={(v) => setF({ ...f, body: v })} testid="sa-item-body" />
          <div className="grid gap-3 sm:grid-cols-3">
            {["news", "history"].includes(kind) && <label className="text-xs text-slate-600">{t("sa_date")}<input type={kind === "news" ? "date" : "text"} placeholder={kind === "history" ? "2026-09" : ""} value={f.date || ""} onChange={(e) => setF({ ...f, date: e.target.value })} className={inp} data-testid="sa-item-date" /></label>}
            {kind === "news" && <label className="text-xs text-slate-600">{t("sa_category")}<select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className={inp} data-testid="sa-item-category">{["notice", "press", "media", "event"].map((c) => <option key={c} value={c}>{t(`news_cat_${c}`)}</option>)}</select></label>}
            {kind !== "news" && <label className="text-xs text-slate-600">{t("sa_order")}<input type="number" value={f.order} onChange={(e) => setF({ ...f, order: Number(e.target.value) })} className={inp} data-testid="sa-item-order" /></label>}
            <label className="flex items-center gap-2 pt-5 text-xs text-slate-600"><input type="checkbox" checked={f.published} onChange={(e) => setF({ ...f, published: e.target.checked })} data-testid="sa-item-published" />{t("sa_published")}</label>
          </div>
          {["service", "news"].includes(kind) && <ImageField value={f.image} onChange={(v) => setF({ ...f, image: v })} testid="sa-item-image" />}
        </div>
        <DialogFooter><Button className="btn-emerald" onClick={save} data-testid="sa-item-save">{t("save")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ItemList({ kind, items, reload }) {
  const { t } = useApp();
  const [edit, setEdit] = useState(null);
  const del = async (id) => { if (!window.confirm(t("delete") + "?")) return; await api.delete(`/platform/site/items/${id}`); clearSiteCache(); reload(); };
  const list = items.filter((i) => i.kind === kind);
  return (
    <Card>
      <div className="mb-3 flex justify-end"><Button size="sm" className="btn-emerald" onClick={() => setEdit({})} data-testid={`sa-add-${kind}`}><Plus className="mr-1 h-4 w-4" />{t("sa_add")}</Button></div>
      <ul className="divide-y divide-slate-100" data-testid={`sa-list-${kind}`}>{list.map((i) => (
        <li key={i.id} className="flex items-center gap-3 py-3 text-sm">
          <span className="w-24 shrink-0 font-num text-xs text-slate-500">{i.date || `#${i.order}`}</span>
          <span className="flex-1 truncate">{i.title?.ja}</span>
          {!i.published && <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">{t("sa_unpublished")}</span>}
          <button className="icon-btn" onClick={() => setEdit(i)} data-testid={`sa-edit-${i.id}`}><Pencil className="h-4 w-4" /></button>
          <button className="icon-btn text-red-600" onClick={() => del(i.id)} data-testid={`sa-delete-${i.id}`}><Trash2 className="h-4 w-4" /></button>
        </li>))}</ul>
      {edit && <ItemDialog kind={kind} item={edit.id ? edit : null} onClose={() => setEdit(null)} onDone={reload} />}
    </Card>
  );
}

export default function SiteAdmin() {
  const { t } = useApp();
  const { data, reload } = useApi("/platform/site");
  const [k, setK] = useState(0);
  useEffect(() => { if (data) setK((x) => x + 1); }, [data]);
  if (!data) return <Spinner />;
  return (
    <div data-testid="site-admin">
      <div className="mb-3 flex justify-end"><a href="/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-[#0B6E4F]" data-testid="sa-view-site">{t("sa_view_site")}<ExternalLink className="h-3.5 w-3.5" /></a></div>
      <Tabs defaultValue="settings">
        <TabsList className="flex-wrap bg-white/70">{["settings", "service", "news", "faq", "history"].map((x) => <TabsTrigger key={x} value={x} data-testid={`sa-tab-${x}`}>{t(`sa_${x}`)}</TabsTrigger>)}</TabsList>
        <TabsContent value="settings" className="mt-4"><SettingsForm key={k} initial={data.settings} onSaved={reload} /></TabsContent>
        {["service", "news", "faq", "history"].map((x) => <TabsContent key={x} value={x} className="mt-4"><ItemList kind={x} items={data.items} reload={reload} /></TabsContent>)}
      </Tabs>
    </div>
  );
}
