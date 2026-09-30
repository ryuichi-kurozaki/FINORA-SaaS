import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Download, Eye, FileSpreadsheet, Lock, MessageSquareWarning, Pencil, Plus, Search, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { useApp } from "@/context/AppContext";
import { api, downloadFile, errMsg, useApi } from "@/lib/api";
import { CURRENCIES, ENTITIES, EXPENSE_CATS, INCOME_CATS, OWNED } from "@/config/entities";
import RecordDrawer from "@/components/RecordDrawer";
import CorrectionDialog from "@/components/CorrectionDialog";
import SecuritySearch from "@/components/SecuritySearch";
import { fmtDate, num, plColor, yen } from "@/lib/format";
import { Card, Empty, Spinner } from "@/components/common";

function Cell({ f, row, assets }) {
  const { t, clientName } = useApp();
  const v = row[f.k];
  if (f.type === "client") return <span className="text-slate-700">{row.client_name || clientName(v) || "—"}</span>;
  if (f.type === "asset") return <span>{assets.find((a) => a.id === v)?.name || "—"}</span>;
  if (f.type === "money") return <span className="font-num">{yen(v)}</span>;
  if (f.type === "pl") return <span className={`font-num ${plColor(v)}`}>{yen(v)}</span>;
  if (f.type === "number") return <span className="font-num">{num(v, 4)}</span>;
  if (f.type === "date") return <span className="font-num text-slate-600">{fmtDate(v)}</span>;
  if (f.type === "user") return <span>{row._userName || "—"}</span>;
  if ((f.type === "select" || f.type === "category") && !f.raw) {
    if (!v) return "—";
    if (f.opts && !f.opts.includes(String(v))) return <span>{typeof v === "number" ? yen(v) : v}</span>;
    return <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{t((f.prefix || "") + v)}</span>;
  }
  return <span className="line-clamp-1 max-w-[260px]">{v || "—"}</span>;
}

const selCls = "h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40";

function Field({ f, form, set, users, accounts, assets }) {
  const { t, clients } = useApp();
  const v = form[f.k] ?? "";
  const id = `field-${f.k}`;
  const on = (e) => set(f.k, e.target.value);
  let input;
  if (f.type === "select" || f.type === "category") {
    const opts = f.type === "category" ? (form.direction === "income" ? INCOME_CATS : EXPENSE_CATS) : f.opts;
    input = <select id={id} data-testid={id} className={selCls} value={v} onChange={on}><option value="">—</option>
      {v !== "" && !opts.includes(String(v)) && <option value={v}>{typeof v === "number" ? yen(v) : v}</option>}
      {opts.map((o) => <option key={o} value={o}>{f.raw ? o : t((f.prefix || "") + o)}</option>)}</select>;
  } else if (f.type === "asset") {
    input = <select id={id} data-testid={id} className={selCls} value={v} onChange={on}><option value="">—</option>{assets.filter((a) => a.client_id === form.client_id).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select>;
  } else if (f.type === "client") {
    input = <select id={id} data-testid={id} className={selCls} value={v} onChange={on}><option value="">—</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.corporate_name || c.name}</option>)}</select>;
  } else if (f.type === "user") {
    input = <select id={id} data-testid={id} className={selCls} value={v} onChange={on}><option value="">—</option>{users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select>;
  } else if (f.type === "account") {
    input = <select id={id} data-testid={id} className={selCls} value={v} onChange={on}><option value="">—</option>{accounts.filter((a) => a.client_id === form.client_id).map((a) => <option key={a.id} value={a.id}>{a.institution} ({a.currency})</option>)}</select>;
  } else if (f.type === "textarea") {
    input = <textarea id={id} data-testid={id} rows={3} className="w-full rounded-lg border border-slate-200 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40" value={v} onChange={on} />;
  } else {
    input = <Input id={id} data-testid={id} type={f.type === "date" ? "date" : ["number", "money"].includes(f.type) ? "number" : "text"} step="any" value={v} onChange={on} className="h-10" />;
  }
  return (
    <label className={`block ${f.wide ? "sm:col-span-2" : ""}`}>
      <span className="mb-1.5 block text-xs font-medium text-slate-600">{t(f.label || f.k)}{f.req && <span className="text-red-500"> *</span>}</span>
      {input}
    </label>
  );
}

export default function EntityManager({ entity, clientId, title, onChange, compact }) {
  const { t, user, canEdit, isClient, scopeClient, refreshClients } = useApp();
  const cid = clientId ?? scopeClient;
  const { data, loading, reload } = useApi(`/data/${entity}${cid ? `?client_id=${cid}` : ""}`, [cid]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({});
  const [del, setDel] = useState(null);
  const [users, setUsers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [assets, setAssets] = useState([]);
  const [detail, setDetail] = useState(null);
  const [corr, setCorr] = useState(null);
  const fileRef = useRef(null);
  const [imp, setImp] = useState(null);
  const canWrite = canEdit(entity);
  const owned = OWNED.includes(entity);
  const fields = ENTITIES[entity].filter((f) => !(f.adminOnly && user.role !== "admin"));
  const cols = fields.filter((f) => f.table && !(clientId && f.type === "client"));

  useEffect(() => {
    if (!isClient) api.get("/users").then((r) => setUsers(r.data)).catch(() => {});
    if (["assets", "transactions"].includes(entity)) api.get("/data/accounts").then((r) => setAccounts(r.data)).catch(() => {});
    if (entity === "transactions") api.get("/data/assets").then((r) => setAssets(r.data)).catch(() => {});
  }, [entity, isClient]);

  const rows = useMemo(() => {
    const um = Object.fromEntries(users.map((u) => [u.id, u.name]));
    const list = (data || []).map((r) => ({ ...r, _userName: um[r.consultant_id || r.assignee_id] }));
    if (!q) return list;
    const s = q.toLowerCase();
    return list.filter((r) => JSON.stringify(r).toLowerCase().includes(s));
  }, [data, q, users]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const openNew = () => { setForm(cid && entity !== "clients" ? { client_id: cid } : {}); setOpen(true); };
  const openNewAcct = (aid) => { setForm({ ...(cid && entity !== "clients" ? { client_id: cid } : {}), ...(aid ? { account_id: aid } : {}) }); setOpen(true); };
  const assetGroups = useMemo(() => {
    if (entity !== "assets") return [];
    const accs = accounts.filter((a) => !cid || a.client_id === cid);
    const gs = accs.map((a) => ({ key: a.id, acctId: a.id, label: `${a.institution || t("account_id")}${a.currency ? ` (${a.currency})` : ""}`, rows: rows.filter((r) => r.account_id === a.id) }));
    const ids = new Set(accs.map((a) => a.id));
    const orphan = rows.filter((r) => !r.account_id || !ids.has(r.account_id));
    if (orphan.length) gs.push({ key: "none", acctId: "", label: t("account_unassigned"), rows: orphan });
    return gs;
  }, [entity, accounts, rows, cid, t]);
  const renderRow = (r) => (
    <tr key={r.id} data-testid={`${entity}-row-${r.id}`}>
      {cols.map((c) => <td key={c.k}><Cell f={c} row={r} assets={assets} /></td>)}
      {owned && <td className="whitespace-nowrap text-[11px] text-slate-500"><span className="font-num">{fmtDate(r.price_date || r.balance_date || r.updated_at)}</span> · {t(r.source || "MANUAL")}</td>}
      <td className="whitespace-nowrap text-right">
        {entity !== "clients" && <button className="icon-btn" onClick={() => setDetail(r)} title={t("view_detail")} data-testid={`${entity}-view-${r.id}`}><Eye className="h-4 w-4" /></button>}
        {owned && !isClient && <button className="icon-btn hover:text-[#C9A227]" onClick={() => setCorr(r)} title={t("request_correction")} data-testid={`${entity}-correction-${r.id}`}><MessageSquareWarning className="h-4 w-4" /></button>}
        {canEdit(entity, r) && <button className="icon-btn" onClick={() => { setForm(r); setOpen(true); }} data-testid={`${entity}-edit-${r.id}`}><Pencil className="h-4 w-4" /></button>}
        {canEdit(entity, r) && (entity !== "clients" || user.role === "admin") && <button className="icon-btn hover:text-red-600" onClick={() => setDel(r)} data-testid={`${entity}-delete-${r.id}`}><Trash2 className="h-4 w-4" /></button>}
      </td>
    </tr>
  );
  const after = () => { reload(); onChange && onChange(); if (entity === "clients") refreshClients(); };

  const save = async () => {
    const miss = fields.filter((f) => f.req && !f.computed && (form[f.k] === undefined || form[f.k] === ""));
    if (miss.length) return toast.error(`${t(miss[0].label || miss[0].k)}${t("required_suffix")}`);
    const body = Object.fromEntries(fields.filter((f) => !f.computed && form[f.k] !== undefined).map((f) => [f.k, form[f.k]]));
    try {
      if (form.id) await api.put(`/data/${entity}/${form.id}`, body);
      else await api.post(`/data/${entity}`, body);
      toast.success(t("saved"));
      setOpen(false);
      after();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const remove = async () => {
    try { await api.delete(`/data/${entity}/${del.id}`); toast.success(t("deleted")); setDel(null); after(); }
    catch (e) { toast.error(errMsg(e)); }
  };

  const doImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    if (cid && entity !== "clients") fd.append("client_id", cid);
    if (imp?.acct) fd.append("account_id", imp.acct);
    try {
      const r = await api.post(`/io/import/${entity}`, fd);
      toast.success(`${r.data.created} ${t("import_done")}${r.data.format ? ` · ${t("import_detected")}: ${t("rakuten_" + r.data.format)}` : ""}${r.data.errors.length ? ` / ${t("import_errors")}: ${r.data.errors.length}` : ""}`);
      after();
    } catch (err) { toast.error(errMsg(err)); }
    e.target.value = "";
    setImp(null);
  };

  const exp = (fmt) => downloadFile(`/io/export/${entity}?fmt=${fmt}${cid ? `&client_id=${cid}` : ""}`, `finora_${entity}.${fmt}`).catch((e) => toast.error(errMsg(e)));

  return (
    <Card className={compact ? "p-4 sm:p-5" : ""} data-testid={`entity-${entity}`}>
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          {title && <h3 className="font-display text-[15px] font-bold text-[#071A2B]">{title}</h3>}
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-num text-xs text-slate-500">{rows.length}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input placeholder={t("search")} value={q} onChange={(e) => setQ(e.target.value)} className="h-9 w-48 pl-9" data-testid={`${entity}-search-input`} />
          </div>
          {user.role !== "consultant" && <>
            <Button variant="outline" size="sm" onClick={() => exp("csv")} data-testid={`${entity}-export-csv`}><Download className="mr-1 h-4 w-4" />CSV</Button>
            <Button variant="outline" size="sm" onClick={() => exp("xlsx")} data-testid={`${entity}-export-xlsx`}><FileSpreadsheet className="mr-1 h-4 w-4" />Excel</Button></>}
          {canWrite && (
            <>
              <Button variant="outline" size="sm" onClick={() => (entity === "assets" ? setImp({ open: true, acct: "" }) : fileRef.current.click())} data-testid={`${entity}-import-btn`}><Upload className="mr-1 h-4 w-4" />{t("import")}</Button>
              <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" hidden onChange={doImport} data-testid={`${entity}-import-input`} />
              <Button size="sm" className="btn-emerald" onClick={openNew} data-testid={`${entity}-add-btn`}><Plus className="mr-1 h-4 w-4" />{t("add")}</Button>
            </>
          )}
        </div>
      </div>
      {owned && !isClient && <div className="mb-3 flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600" data-testid={`${entity}-readonly-note`}><Lock className="h-3.5 w-3.5 text-[#C9A227]" />{t("readonly_note")}</div>}
      {loading ? <Spinner /> : (entity !== "assets" && !rows.length) ? <Empty text={t("no_data")} /> : (
        <div className="-mx-2 overflow-x-auto">
          <table className="data-table w-full min-w-[720px] text-sm" data-testid={`${entity}-table`}>
            <thead><tr>{cols.map((c) => <th key={c.k}>{t(c.label || c.k)}</th>)}{owned && <th>{t("last_updated")}</th>}<th className="text-right">{t("actions")}</th></tr></thead>
            <tbody>
              {entity === "assets" ? assetGroups.map((g) => (
                <Fragment key={g.key}>
                  <tr className="bg-slate-50" data-testid={`assets-group-${g.key}`}>
                    <td colSpan={cols.length + (owned ? 1 : 0) + 1} className="!py-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-[#071A2B]">{g.label} <span className="ml-1 font-num text-slate-400">({g.rows.length})</span></span>
                        {canWrite && <button className="text-xs font-medium text-[#0B6E4F] hover:underline" onClick={() => openNewAcct(g.acctId)} data-testid={`assets-add-to-${g.key}`}>＋ {t("add")}</button>}
                      </div>
                    </td>
                  </tr>
                  {g.rows.length ? g.rows.map(renderRow) : <tr><td colSpan={cols.length + (owned ? 1 : 0) + 1} className="!py-2 text-center text-xs text-slate-400">{t("no_data")}</td></tr>}
                </Fragment>
              )) : rows.map(renderRow)}
            </tbody>
          </table>
        </div>
      )}
      <RecordDrawer row={detail} entity={entity} onClose={() => setDetail(null)} onCorrection={owned ? (r) => { setDetail(null); setCorr(r); } : null} />
      <CorrectionDialog open={!!corr} onOpenChange={(o) => !o && setCorr(null)} clientId={corr?.client_id} entity={entity} targetId={corr?.id} targetLabel={corr?.name || corr?.institution || corr?.tx_type} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" data-testid={`${entity}-form-dialog`}>
          <DialogHeader><DialogTitle className="font-display">{form.id ? t("edit") : t("add")} — {t(entity)}</DialogTitle></DialogHeader>
          {entity === "assets" && <SecuritySearch key={form.id || "new"} form={form} set={set} />}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {fields.filter((f) => !f.computed && !(clientId && f.type === "client") && !(isClient && f.type === "client")).map((f) => <Field key={f.k} f={f} form={form} set={set} users={users} accounts={accounts} assets={assets} />)}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} data-testid={`${entity}-form-cancel`}>{t("cancel")}</Button>
            <Button className="btn-emerald" onClick={save} data-testid={`${entity}-form-save`}>{t("save")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AlertDialog open={!!del} onOpenChange={(o) => !o && setDel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>{t("delete")}</AlertDialogTitle><AlertDialogDescription>{t("confirm_delete")}</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="confirm-delete-cancel">{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={remove} data-testid="confirm-delete-ok">{t("delete")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <Dialog open={!!imp?.open} onOpenChange={(o) => !o && setImp(null)}>
        <DialogContent data-testid="asset-import-dialog">
          <DialogHeader><DialogTitle className="font-display">{t("import")} — {t(entity)}</DialogTitle></DialogHeader>
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-600">{t("account_id")}</span>
            <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm" value={imp?.acct || ""} onChange={(e) => setImp((v) => ({ ...v, acct: e.target.value }))} data-testid="asset-import-account">
              <option value="">{t("import_account_none")}</option>
              {accounts.filter((a) => !cid || a.client_id === cid).map((a) => <option key={a.id} value={a.id}>{a.institution} ({a.currency})</option>)}
            </select>
          </label>
          <p className="text-xs text-slate-500">{t("import_account_hint")}</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setImp(null)} data-testid="asset-import-cancel">{t("cancel")}</Button>
            <Button className="btn-emerald" onClick={() => { setImp((v) => ({ ...v, open: false })); fileRef.current.click(); }} data-testid="asset-import-choose-file"><Upload className="mr-1 h-4 w-4" />{t("import_choose_file")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
