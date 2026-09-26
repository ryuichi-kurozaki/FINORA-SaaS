import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardTitle, PageHeader } from "@/components/common";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDate, fmtDateTime, yen } from "@/lib/format";
import { StatusPill } from "@/components/econtract/EContractPanel";
import SignaturePad from "@/components/econtract/SignaturePad";

const STEPS = ["DRAFT", "IMPORTANT_INFO_SENT", "IMPORTANT_INFO_CONFIRMED", "CONTRACT_SENT", "FIRST_PARTY_SIGNED", "BOTH_SIGNED", "ACTIVE"];
const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm";

function Stepper({ s, t }) {
  const i = STEPS.indexOf(s);
  return <div className="mb-6 flex flex-wrap gap-1.5" data-testid="ec-stepper">{STEPS.map((x, k) => <span key={x} className={`rounded-full px-2.5 py-1 text-[11px] ${k <= i && i >= 0 ? "bg-[#071A2B] text-white" : "bg-slate-100 text-slate-400"}`}>{k + 1}. {t(`ec_${x}`)}</span>)}</div>;
}

function DocView({ doc, sections, t, onSeen }) {
  const seen = useRef(false);
  useEffect(() => { if (doc && onSeen && !seen.current) { seen.current = true; onSeen(doc.id); } }, [doc, onSeen]);
  return (
    <div className="max-h-[480px] space-y-3 overflow-y-auto rounded-xl border border-slate-100 bg-slate-50/60 p-5" data-testid={`ec-doc-${doc?.document_type || "preview"}`}>
      {doc && <div className="font-num text-[11px] text-slate-500">{doc.number} · v{doc.version} · SHA-256 {doc.hash.slice(0, 16)}… {doc.integrity_ok ? "✓" : "⚠"}</div>}
      {(doc?.sections || sections || []).map((s) => <div key={s.key}><div className="text-sm font-semibold text-[#0B6E4F]">{s.title}</div><div className="whitespace-pre-wrap text-sm text-slate-700">{s.body}</div></div>)}
    </div>
  );
}

function SignForm({ onSign, t }) {
  const [name, setName] = useState("");
  const [png, setPng] = useState("");
  const [ok, setOk] = useState(false);
  return (
    <div className="space-y-3 rounded-xl border border-emerald-100 p-4" data-testid="ec-sign-form">
      <label className="text-xs text-slate-600">{t("ec_signer_name")}<input className={inp} value={name} onChange={(e) => setName(e.target.value)} data-testid="ec-sign-name" /></label>
      <div className="text-xs text-slate-600">{t("ec_handwritten")}</div><SignaturePad onChange={setPng} t={t} />
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} data-testid="ec-sign-agree" />{t("ec_sign_agree")}</label>
      <Button className="btn-emerald" disabled={!name || !png || !ok} onClick={() => onSign({ name, signature_png: png, agree: true })} data-testid="ec-sign-submit">{t("ec_sign")}</Button>
    </div>
  );
}

function IssuerTools({ d, act, t }) {
  const saas = d.contract_type === "FINORA_SAAS";
  const [end, setEnd] = useState(null);
  const [fields, setFields] = useState({});
  const saveDraft = () => act("", { method: "put", body: { contract_type: d.contract_type, client_id: d.client_id, tenant_id: d.tenant_id, lang: d.lang, terms: d.terms, fields: { ...d.fields, ...fields } } });
  return (
    <div className="space-y-3">
      {d.status === "DRAFT" && d.preview && <details className="rounded-xl border border-slate-100 p-3" data-testid="ec-edit-sections"><summary className="cursor-pointer text-sm font-medium">{t("ec_edit_sections")}</summary>
        {d.preview.important.concat(d.preview.agreement.filter((s) => !d.preview.important.some((x) => x.key === s.key))).map((s) => (
          <label key={s.key} className="mt-2 block text-xs text-slate-600">{s.title}<textarea className={`${inp} h-16 py-1`} defaultValue={s.body} onChange={(e) => setFields({ ...fields, [s.key]: e.target.value })} data-testid={`ec-field-${s.key}`} /></label>))}
        <Button variant="outline" className="mt-2" onClick={saveDraft} data-testid="ec-save-draft">{t("save")}</Button></details>}
      <div className="flex flex-wrap gap-2">
        {d.status === "DRAFT" && <Button className="btn-emerald" onClick={() => act("send-important")} data-testid="ec-send-important">{t("ec_send_important")}</Button>}
        {d.status === "IMPORTANT_INFO_CONFIRMED" && <Button className="btn-emerald" onClick={() => act("send-agreement")} data-testid="ec-send-agreement">{t("ec_send_agreement")}</Button>}
        {["ACTIVE", "PAUSED"].includes(d.status) && <>
          <Button variant="outline" onClick={() => act("amend")} data-testid="ec-amend">{t("ec_amend")}</Button>
          <Button variant="outline" onClick={() => act("pause")} data-testid="ec-pause">{t(d.status === "PAUSED" ? "ec_resume" : "ec_pause")}</Button>
          <Button variant="outline" className="text-red-600" onClick={() => setEnd({ end_date: new Date().toISOString().slice(0, 10), reason: "", consultant_login: "read_only", client_access: "read_only", retention_days: 90 })} data-testid="ec-end">{t("ec_end_contract")}</Button></>}
        {STEPS.slice(0, 6).includes(d.status) && <Button variant="outline" className="text-red-600" onClick={() => act("cancel", { body: { reason: "" } })} data-testid="ec-cancel">{t("ec_cancel")}</Button>}
      </div>
      {end && <div className="grid gap-2 rounded-xl border border-red-100 p-4 sm:grid-cols-2" data-testid="ec-end-form">
        <label className="text-xs">{t("ec_end")}<input type="date" className={inp} value={end.end_date} onChange={(e) => setEnd({ ...end, end_date: e.target.value })} data-testid="ec-end-date" /></label>
        <label className="text-xs">{t("ec_end_reason")}<input className={inp} value={end.reason} onChange={(e) => setEnd({ ...end, reason: e.target.value })} data-testid="ec-end-reason" /></label>
        {saas && ["consultant_login", "client_access"].map((k) => <label key={k} className="text-xs">{t(`ec_${k}`)}<select className={inp} value={end[k]} onChange={(e) => setEnd({ ...end, [k]: e.target.value })} data-testid={`ec-end-${k}`}><option value="read_only">{t("ec_read_only")}</option><option value="blocked">{t("ec_blocked")}</option></select></label>)}
        {saas && <label className="text-xs">{t("ec_retention")}<input type="number" className={inp} value={end.retention_days} onChange={(e) => setEnd({ ...end, retention_days: Number(e.target.value) })} data-testid="ec-end-retention" /></label>}
        <Button className="bg-red-600 text-white hover:bg-red-700 sm:col-span-2" disabled={!end.reason} onClick={() => act("end", { body: end }).then(() => setEnd(null))} data-testid="ec-end-submit">{t("ec_end_contract")}</Button></div>}
    </div>
  );
}

export default function EContractDetail() {
  const { id } = useParams();
  const { t } = useApp();
  const { data: d, reload } = useApi(`/econtracts/${id}`);
  const [ok, setOk] = useState(false);
  if (!d) return <div className="p-8 text-sm text-slate-400">…</div>;
  const docs = Object.fromEntries((d.documents || []).map((x) => [x.document_type.includes("AGREEMENT") ? "agreement" : "important", x]));
  const act = async (path, { method = "post", body } = {}) => {
    try {
      const { data } = await api[method](`/econtracts/${id}${path ? `/${path}` : ""}`, body);
      toast.success(t("saved"));
      if (path === "amend") window.location.assign(`/econtracts/${data.id}`); else reload();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const seen = d.can_receive ? (docId) => api.post(`/econtracts/${id}/view/${docId}`).catch(() => {}) : null;
  const pdf = async (doc) => {
    const { data } = await api.get(`/econtracts/${id}/docs/${doc.id}/pdf`, { responseType: "blob" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(data); a.download = doc.pdf_filename || `${doc.number}.pdf`; a.click();
  };
  const saas = d.contract_type === "FINORA_SAAS";
  const timeline = [...(d.acts || []).map((a) => ({ at: a.at, who: a.user_email, what: `${a.act} · ${a.document_type} v${a.document_version}`, ip: a.ip })),
    ...(d.history || []).map((h) => ({ at: h.at, who: h.user_email, what: `${h.action} · ${h.after?.status || h.after?.document_type || ""}`, ip: h.ip }))].sort((a, b) => (a.at < b.at ? -1 : 1));
  const info = [["ec_type", t(saas ? "ec_finora_contract" : "ec_client_contract")], [saas ? "tenants" : "client", saas ? d.tenant_name : d.client_name], ["ec_service", d.terms.service_name],
    ["ec_fee", saas ? yen(d.fee_amount) : `${yen(d.terms.fee)} / ${t(`cyc_${d.terms.fee_type}`)}`], ["ec_start", fmtDate(d.terms.start_date)], ["ec_end", fmtDate(d.end_date || d.terms.end_date)],
    ["ec_next_invoice", fmtDate(d.next_invoice_date)], ["ec_activated", fmtDateTime(d.activated_at)]];
  return (
    <div data-testid="econtract-detail">
      <PageHeader eyebrow={saas ? "FINORA_SAAS" : "CONSULTING"} title={`${d.number} v${d.version}`} sub={t(saas ? "ec_saas_note" : "ec_consulting_note")}><StatusPill s={d.status} t={t} /></PageHeader>
      <Stepper s={d.status} t={t} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {d.can_receive && d.status === "IMPORTANT_INFO_SENT" && docs.important && <Card data-testid="ec-confirm-card"><CardTitle>{docs.important.title}</CardTitle>
            <DocView doc={docs.important} t={t} onSeen={seen} />
            <label className="mt-4 flex items-start gap-2 text-sm"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} data-testid="ec-confirm-check" />{t("ec_confirm_text")}</label>
            <Button className="btn-emerald mt-3" disabled={!ok} onClick={() => act("confirm")} data-testid="ec-confirm-btn">{t("ec_confirm_next")}</Button></Card>}
          {d.can_receive && d.status === "CONTRACT_SENT" && docs.agreement && <Card data-testid="ec-recipient-sign-card"><CardTitle>{docs.agreement.title}</CardTitle>
            <DocView doc={docs.agreement} t={t} onSeen={seen} /><div className="mt-4"><SignForm t={t} onSign={(b) => act("sign", { body: b })} /></div></Card>}
          {d.can_issue && d.status === "FIRST_PARTY_SIGNED" && <Card data-testid="ec-issuer-sign-card"><CardTitle>{t("ec_issuer_sign_title")}</CardTitle><SignForm t={t} onSign={(b) => act("sign", { body: b })} /></Card>}
          {d.can_issue && <Card><CardTitle>{t("ec_actions")}</CardTitle><IssuerTools d={d} act={act} t={t} /></Card>}
          {["important", "agreement"].map((k) => (docs[k] || d.preview) && <Card key={k}><CardTitle right={docs[k]?.pdf_file_id && <Button variant="outline" onClick={() => pdf(docs[k])} data-testid={`ec-pdf-${k}`}><Download className="mr-1 h-4 w-4" />PDF</Button>}>
            {docs[k]?.title || t(k === "important" ? "ec_important" : "ec_agreement")} {!docs[k] && <span className="text-xs text-slate-400">({t("ec_preview")})</span>}</CardTitle>
            <DocView doc={docs[k]} sections={d.preview?.[k]} t={t} /></Card>)}
        </div>
        <div className="space-y-6">
          <Card><CardTitle>{t("ec_summary")}</CardTitle><dl className="grid grid-cols-2 gap-2 text-sm" data-testid="ec-summary">{info.flatMap(([k, v]) => [<dt key={`${k}-t`} className="text-slate-500">{t(k)}</dt>, <dd key={`${k}-v`} className="font-num">{v || "—"}</dd>])}</dl></Card>
          <Card><CardTitle>{t("ec_versions")}</CardTitle>{(d.versions || []).map((v) => <a key={v.id} href={`/econtracts/${v.id}`} className="flex justify-between py-1 text-sm hover:underline" data-testid={`ec-version-${v.version}`}><span>v{v.version}</span><StatusPill s={v.status} t={t} /></a>)}</Card>
          <Card><CardTitle>{t("ec_evidence")}</CardTitle><ol className="max-h-[520px] space-y-2 overflow-y-auto text-xs" data-testid="ec-evidence">{timeline.map((x, i) => <li key={i} className="border-l-2 border-emerald-200 pl-2"><div className="font-num text-slate-400">{fmtDateTime(x.at)} · {x.ip}</div><div>{x.what}</div><div className="text-slate-500">{x.who}</div></li>)}</ol></Card>
        </div>
      </div>
    </div>
  );
}
