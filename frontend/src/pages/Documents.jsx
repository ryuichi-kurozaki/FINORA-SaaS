import { useRef, useState } from "react";
import { Download, FileText, ImageIcon, Trash2, UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, downloadFile, errMsg, useApi } from "@/lib/api";
import { DOC_CATS } from "@/config/entities";
import { bytes, fmtDateTime } from "@/lib/format";
import { Card, CardTitle, Empty, PageHeader, Spinner } from "@/components/common";
import { useScopeLabel } from "@/lib/useDashboard";

export function DocumentsPanel({ clientId }) {
  const { t, isClient, clients, clientName } = useApp();
  const canWrite = isClient;
  const { data, loading, reload } = useApi(`/documents${clientId ? `?client_id=${clientId}` : ""}`, [clientId]);
  const [cid, setCid] = useState(clientId || "");
  const [cat, setCat] = useState("contract");
  const [meta, setMeta] = useState({ fiscal_year: "", institution: "", expiry_date: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const upload = async () => {
    const f = fileRef.current.files[0];
    const target = clientId || cid;
    if (!f || !target) return toast.error(`${t("client")} / ${t("file")}${t("required_suffix")}`);
    const fd = new FormData();
    fd.append("file", f); fd.append("client_id", target); fd.append("category", cat);
    Object.entries(meta).forEach(([k, v]) => fd.append(k, v));
    setBusy(true);
    try { await api.post("/documents", fd); toast.success(t("saved")); fileRef.current.value = ""; reload(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const remove = async (d) => {
    if (!window.confirm(t("confirm_delete"))) return;
    try { await api.delete(`/documents/${d.id}`); toast.success(t("deleted")); reload(); } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="space-y-6" data-testid="documents-panel">
      {canWrite && (
        <Card>
          <CardTitle>{t("upload")}</CardTitle>
          <div className="grid gap-3 md:grid-cols-[1fr_1fr_2fr_auto] md:items-end">
            {!clientId && (
              <select value={cid} onChange={(e) => setCid(e.target.value)} className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" data-testid="doc-client-select">
                <option value="">{t("client")}…</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.corporate_name || c.name}</option>)}
              </select>
            )}
            <select value={cat} onChange={(e) => setCat(e.target.value)} className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" data-testid="doc-category-select">
              {DOC_CATS.map((c) => <option key={c} value={c}>{t(c)}</option>)}
            </select>
            <input ref={fileRef} type="file" className="h-10 rounded-lg border border-dashed border-slate-300 bg-white px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-2 file:text-xs" data-testid="doc-file-input" />
            <Button className="btn-emerald h-10" onClick={upload} disabled={busy} data-testid="doc-upload-btn"><UploadCloud className="mr-1 h-4 w-4" />{t("upload")}</Button>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-4">
            {[["fiscal_year", "text"], ["institution", "text"], ["expiry_date", "date"], ["notes", "text"]].map(([k, ty]) => (
              <label key={k} className="text-xs text-slate-600">{t(k)}<input type={ty} value={meta[k]} onChange={(e) => setMeta({ ...meta, [k]: e.target.value })} className="mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" data-testid={`doc-meta-${k}`} /></label>
            ))}
          </div>
        </Card>
      )}
      <Card>
        {loading ? <Spinner /> : !data?.length ? <Empty text={t("no_data")} /> : (
          <div className="-mx-2 overflow-x-auto">
            <table className="data-table w-full min-w-[700px] text-sm" data-testid="documents-table">
              <thead><tr>{["filename", "category", "fiscal_year", "institution", "expiry_date", "client", "size", "uploaded_by", "date", "actions"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
              <tbody>
                {data.map((d) => (
                  <tr key={d.id} data-testid={`doc-row-${d.id}`}>
                    <td className="font-medium"><span className="inline-flex items-center gap-2">{d.content_type.startsWith("image/") ? <ImageIcon className="h-4 w-4 text-[#C9A227]" /> : <FileText className="h-4 w-4 text-[#00A878]" />}{d.filename}</span></td>
                    <td>{t(d.category)}</td><td className="font-num">{d.fiscal_year || "—"}</td><td>{d.institution || "—"}</td><td className="font-num">{d.expiry_date || "—"}</td><td>{clientName(d.client_id)}</td><td className="font-num">{bytes(d.size)}</td><td className="text-slate-500">{d.uploaded_by}</td>
                    <td className="font-num text-slate-500">{fmtDateTime(d.created_at)}</td>
                    <td className="whitespace-nowrap">
                      <button className="icon-btn" onClick={() => downloadFile(`/documents/${d.id}/download`, d.filename)} data-testid={`doc-download-${d.id}`}><Download className="h-4 w-4" /></button>
                      {canWrite && <button className="icon-btn hover:text-red-600" onClick={() => remove(d)} data-testid={`doc-delete-${d.id}`}><Trash2 className="h-4 w-4" /></button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

export default function Documents() {
  const { t, scopeClient } = useApp();
  const scope = useScopeLabel();
  return (
    <div data-testid="documents-page">
      <PageHeader eyebrow={`Documents · ${scope}`} title={t("documents")} />
      <DocumentsPanel key={scopeClient} clientId={scopeClient} />
    </div>
  );
}
