import { TwoFactorCard, ConsentHistory } from "@/components/SecurityExtras";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp } from "@/context/AppContext";
import { api, downloadFile, errMsg, useApi } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { Card, CardTitle, LevelBadge, PageHeader } from "@/components/common";

function Security() {
  const { t } = useApp();
  const [f, setF] = useState({ current_password: "", new_password: "" });
  const { data: sess, reload } = useApi("/security/sessions");
  const { data: hist } = useApi("/security/login-history");
  const change = async () => {
    try { await api.post("/auth/change-password", f); toast.success(t("saved")); setF({ current_password: "", new_password: "" }); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <TwoFactorCard />
      <ConsentHistory />
      <Card>
        <CardTitle>{t("change_password")}</CardTitle>
        <div className="space-y-3">
          <Input type="password" placeholder={t("current_password")} value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} data-testid="current-password-input" />
          <Input type="password" placeholder={t("new_password")} value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} data-testid="new-password-input" />
          <Button className="btn-emerald" onClick={change} data-testid="change-password-btn">{t("save")}</Button>
        </div>
      </Card>
      <Card>
        <CardTitle>{t("sessions")}</CardTitle>
        <ul className="space-y-2 text-sm">
          {(sess || []).map((s) => (
            <li key={s.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2">
              <div className="min-w-0"><div className="truncate font-num text-xs">{s.ip} · {fmtDateTime(s.created_at)}</div><div className="truncate text-[11px] text-slate-400">{s.ua}</div></div>
              {s.current ? <LevelBadge level="ok">{t("current_session")}</LevelBadge> : <Button variant="outline" size="sm" onClick={() => api.delete(`/security/sessions/${s.id}`).then(reload)} data-testid={`revoke-session-${s.id}`}>{t("revoke")}</Button>}
            </li>
          ))}
        </ul>
      </Card>
      <Card className="xl:col-span-2">
        <CardTitle>{t("login_history")}</CardTitle>
        <div className="-mx-2 max-h-96 overflow-auto">
          <table className="data-table w-full text-sm" data-testid="login-history-table">
            <thead><tr>{["when", "email", "ip", "status", "anomaly"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
            <tbody>{(hist || []).map((h) => (
              <tr key={h.id}><td className="font-num text-xs">{fmtDateTime(h.at)}</td><td>{h.email}</td><td className="font-num text-xs">{h.ip}</td>
                <td><LevelBadge level={h.success ? "ok" : "danger"}>{t(h.success ? "success" : "failed")}</LevelBadge></td>
                <td>{h.anomaly ? <LevelBadge level="warn">{h.reason}</LevelBadge> : "—"}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Users() {
  const { t, clients } = useApp();
  const { data, reload } = useApi("/users");
  const [f, setF] = useState({ role: "consultant" });
  const create = async () => {
    try { await api.post("/users", f); toast.success(t("saved")); setF({ role: "consultant" }); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const toggle = async (u) => { try { await api.put(`/users/${u.id}`, { active: !u.active }); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const sel = "h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm";
  return (
    <Card>
      <CardTitle>{t("users")}</CardTitle>
      <div className="mb-5 grid gap-2 md:grid-cols-6">
        <Input placeholder={t("name")} value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="new-user-name" />
        <Input placeholder={t("email")} value={f.email || ""} onChange={(e) => setF({ ...f, email: e.target.value })} data-testid="new-user-email" />
        <Input type="password" placeholder={t("password")} value={f.password || ""} onChange={(e) => setF({ ...f, password: e.target.value })} data-testid="new-user-password" />
        <select className={sel} value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} data-testid="new-user-role">
          <option value="admin">{t("admin")}</option><option value="consultant">{t("consultant")}</option><option value="client">{t("client_role")}</option>
        </select>
        <select className={sel} disabled={f.role !== "client"} value={f.client_id || ""} onChange={(e) => setF({ ...f, client_id: e.target.value })} data-testid="new-user-client">
          <option value="">{t("client")}…</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.corporate_name || c.name}</option>)}
        </select>
        <Button className="btn-emerald h-10" onClick={create} data-testid="new-user-submit">{t("new_user")}</Button>
      </div>
      <div className="-mx-2 overflow-x-auto">
        <table className="data-table w-full text-sm" data-testid="users-table">
          <thead><tr>{["name", "email", "role", "status", "when", "actions"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
          <tbody>{(data || []).map((u) => (
            <tr key={u.id}><td className="font-medium">{u.name}</td><td>{u.email}</td><td>{t(u.role === "client" ? "client_role" : u.role)}</td>
              <td><LevelBadge level={u.active ? "ok" : "info"}>{t(u.active ? "active" : "inactive")}</LevelBadge></td><td className="font-num text-xs">{fmtDateTime(u.last_login)}</td>
              <td><Button variant="outline" size="sm" onClick={() => toggle(u)} data-testid={`user-toggle-${u.id}`}>{t(u.active ? "inactive" : "active")}</Button></td></tr>
          ))}</tbody>
        </table>
      </div>
    </Card>
  );
}

function short(o) {
  if (!o) return "—";
  const { id, tenant_id, created_at, updated_at, created_by, ...rest } = o;
  return JSON.stringify(rest).slice(0, 140);
}

function Audit() {
  const { t } = useApp();
  const { data } = useApi("/security/audit-logs");
  return (
    <Card>
      <CardTitle>{t("audit_logs")}</CardTitle>
      <div className="-mx-2 max-h-[600px] overflow-auto">
        <table className="data-table w-full text-xs" data-testid="audit-table">
          <thead><tr>{["when", "who", "what", "before", "after", "ip"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
          <tbody>{(data || []).map((a) => (
            <tr key={a.id}><td className="font-num">{fmtDateTime(a.at)}</td><td>{a.user_email}</td>
              <td><span className="rounded bg-slate-100 px-1.5 py-0.5 font-semibold">{a.action}</span> {a.entity}</td>
              <td className="max-w-[260px] truncate font-num text-slate-500" title={short(a.before)}>{short(a.before)}</td>
              <td className="max-w-[260px] truncate font-num text-slate-700" title={short(a.after)}>{short(a.after)}</td><td className="font-num">{a.ip}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </Card>
  );
}

function Fx() {
  const { t, user } = useApp();
  const [fx, setFx] = useState({});
  useEffect(() => { api.get("/settings").then((r) => setFx(r.data.fx)); }, []);
  const save = async () => { try { const r = await api.put("/settings", { fx }); setFx(r.data.fx); toast.success(t("saved")); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Card>
      <CardTitle>{t("fx_rates")}</CardTitle>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {Object.entries(fx).map(([k, v]) => (
          <label key={k} className="block"><span className="mb-1 block font-num text-xs text-slate-500">{k}/JPY</span>
            <Input type="number" step="any" disabled={user.role !== "admin" || k === "JPY"} value={v} onChange={(e) => setFx({ ...fx, [k]: e.target.value })} data-testid={`fx-${k}`} /></label>
        ))}
      </div>
      {user.role === "admin" && <Button className="btn-emerald mt-4" onClick={save} data-testid="fx-save-btn">{t("save")}</Button>}
    </Card>
  );
}

function DataIO() {
  const { t } = useApp();
  const ents = ["clients", "accounts", "assets", "liabilities", "cashflows", "consulting", "tasks"];
  return (
    <Card>
      <CardTitle>{t("data_io")}</CardTitle>
      <p className="mb-4 text-xs text-slate-500">{t("import_hint")}</p>
      <div className="grid gap-2 md:grid-cols-2">
        {ents.map((e) => (
          <div key={e} className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-2.5">
            <span className="text-sm font-medium">{t(e === "cashflows" ? "cashflow" : e)}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => downloadFile(`/io/export/${e}?fmt=csv`, `finora_${e}.csv`)} data-testid={`io-export-csv-${e}`}>CSV</Button>
              <Button variant="outline" size="sm" onClick={() => downloadFile(`/io/export/${e}?fmt=xlsx`, `finora_${e}.xlsx`)} data-testid={`io-export-xlsx-${e}`}>Excel</Button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

const FLOW = ["clients", "accounts", "assets", "cashflow", "portfolio", "analytics", "risk", "simulation", "ai_insight", "consulting", "reports"];
const MATRIX = [["clients", "CRUD", "CRUD*", "R*"], ["assets / accounts / liabilities", "CRUD", "CRUD*", "R*"], ["AI / reports", "✓", "✓*", "✓*"], ["users / audit logs", "✓", "—", "—"], ["export / import", "✓", "✓*", "—"]];

function System() {
  const { t } = useApp();
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card>
        <CardTitle>{t("data_flow")}</CardTitle>
        <div className="flex flex-wrap items-center gap-2 text-xs">{FLOW.map((k, i) => <span key={k} className="flex items-center gap-2"><span className="rounded-lg bg-[#071A2B] px-2.5 py-1 text-white">{t(k)}</span>{i < FLOW.length - 1 && <span className="text-[#00A878]">→</span>}</span>)}</div>
        <CardTitle><span className="mt-6 block">{t("modules")}</span></CardTitle>
        <ul className="space-y-1 font-num text-xs text-slate-600">
          <li>core.py — DB, JWT, RBAC, tenant scope, field encryption (Fernet), audit</li><li>auth_routes.py — login, sessions, brute-force lock, users, logs</li>
          <li>crud.py — generic multi-tenant entity API</li><li>analytics.py — portfolio, cash flow, metrics, simulation, risk</li>
          <li>ai_engine.py — AI Intelligence (pluggable engine)</li><li>io_routes.py — CSV/Excel I/O, documents (GridFS)</li>
        </ul>
      </Card>
      <Card>
        <CardTitle>{t("permissions")}</CardTitle>
        <table className="data-table w-full text-xs"><thead><tr><th /><th>{t("admin")}</th><th>{t("consultant")}</th><th>{t("client_role")}</th></tr></thead>
          <tbody>{MATRIX.map((r) => <tr key={r[0]}>{r.map((c, i) => <td key={i} className={i ? "font-num" : "font-medium"}>{c}</td>)}</tr>)}</tbody></table>
        <p className="mt-3 text-[11px] text-slate-500">* assigned / own clients only</p>
      </Card>
    </div>
  );
}

function Inquiries() {
  const { t } = useApp();
  const { data, reload } = useApi("/inquiries");
  const setStatus = async (id, status) => { try { await api.put(`/inquiries/${id}`, { status }); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Card>
      <CardTitle>{t("inquiries")}</CardTitle>
      <div className="space-y-3" data-testid="inquiries-list">
        {!(data || []).length && <div className="py-8 text-center text-sm text-slate-400">{t("no_data")}</div>}
        {(data || []).map((q) => (
          <div key={q.id} className="rounded-xl border border-slate-200 p-4" data-testid={`inquiry-${q.id}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-[#071A2B]">{q.name}</span>{q.company && <span className="text-sm text-slate-500">／{q.company}</span>}
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px]">{t(q.inquiry_type)}</span>
              <span className="text-xs text-slate-400">{q.lang?.toUpperCase()}</span>
              <select value={q.status} onChange={(e) => setStatus(q.id, e.target.value)} className="ml-auto h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs" data-testid={`inquiry-status-${q.id}`}>
                <option value="new">{t("new_status")}</option><option value="in_progress">{t("in_progress")}</option><option value="done">{t("done")}</option>
              </select>
            </div>
            <div className="mt-1 text-xs text-slate-500"><a href={`mailto:${q.email}`} className="text-[#00A878]">{q.email}</a>{q.phone && ` · ${q.phone}`} · <span className="font-num">{fmtDateTime(q.created_at)}</span></div>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{q.message}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function SettingsPage() {
  const { t, user } = useApp();
  const tabs = [["security", Security], ["fx_rates", Fx], ...(user.role !== "client" ? [["data_io", DataIO]] : []), ...(user.role === "admin" ? [["users", Users], ["audit_logs", Audit], ["inquiries", Inquiries]] : []), ["system", System]];
  return (
    <div data-testid="settings-page">
      <PageHeader eyebrow="Settings" title={t("settings")} />
      <Tabs defaultValue="security">
        <TabsList className="h-auto flex-wrap justify-start bg-white/70 p-1">
          {tabs.map(([k]) => <TabsTrigger key={k} value={k} data-testid={`settings-tab-${k}`} className="data-[state=active]:bg-[#071A2B] data-[state=active]:text-white">{t(k)}</TabsTrigger>)}
        </TabsList>
        {tabs.map(([k, C]) => <TabsContent key={k} value={k} className="mt-5"><C /></TabsContent>)}
      </Tabs>
    </div>
  );
}
