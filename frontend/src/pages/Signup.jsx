import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { LogoFull } from "@/components/Logo";
import { PasswordInput } from "@/components/PasswordInput";

const inp = "mt-1 h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40";

function useAutoLogin() {
  const { setUser } = useApp();
  const nav = useNavigate();
  return async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("finora_token", data.access_token);
    const me = await api.get("/auth/me");
    setUser(me.data);
    nav("/");
  };
}

function Shell({ title, sub, children }) {
  const { t, lang, setLang } = useApp();
  return (
    <div className="min-h-screen bg-[#F7F9FC] px-4 py-10">
      <div className="mx-auto max-w-xl">
        <div className="mb-6 flex items-center justify-between"><Link to="/"><LogoFull className="h-12 w-auto" /></Link>
          <div className="flex gap-1">{["ja", "en", "pt"].map((l) => <button key={l} onClick={() => setLang(l)} className={`rounded px-2 py-1 text-xs ${lang === l ? "bg-[#071A2B] text-white" : "text-slate-500"}`}>{l.toUpperCase()}</button>)}</div></div>
        <div className="glass-card rounded-3xl p-8">
          <h1 className="font-display text-2xl font-bold text-[#071A2B]">{title}</h1>
          {sub && <p className="mt-1 text-sm text-slate-500">{sub}</p>}
          <div className="mt-6">{children}</div>
        </div>
        <p className="mt-4 text-center text-xs text-slate-500">{t("have_account")} <Link to="/login" className="text-[#00A878]">{t("login")}</Link></p>
      </div>
    </div>
  );
}

export function Signup() {
  const { t, user } = useApp();
  const login = useAutoLogin();
  const { data: plans } = useApi("/public/plans");
  const [f, setF] = useState({ name: "", company_name: "", entity_type: "individual", email: "", phone: "", address: "", profile: "", qualifications: "", plan_code: "TRIAL", password: "" });
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    try { await api.post("/public/signup", f); await login(f.email, f.password); } catch (err) { toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  const field = (k, label, type = "text", req = false) => <label key={k} className="text-xs text-slate-600">{t(label)}{req && " *"}<input type={type} required={req} value={f[k]} onChange={set(k)} className={inp} data-testid={`signup-${k}`} /></label>;
  return (
    <Shell title={t("signup")} sub={t("signup_sub")}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" data-testid="signup-form">
        {field("name", "name", "text", true)}{field("company_name", "company_name")}
        <label className="text-xs text-slate-600">{t("entity_type")}<select value={f.entity_type} onChange={set("entity_type")} className={inp} data-testid="signup-entity_type"><option value="individual">{t("individual")}</option><option value="corporate">{t("corporate")}</option></select></label>
        {field("email", "email", "email", true)}{field("phone", "phone")}{field("address", "address")}
        {field("qualifications", "qualifications")}
        <label className="text-xs text-slate-600">{t("plan")}<select value={f.plan_code} onChange={set("plan_code")} className={inp} data-testid="signup-plan">{(plans || []).map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select></label>
        <label className="text-xs text-slate-600 sm:col-span-2">{t("profile_text")}<textarea value={f.profile} onChange={set("profile")} rows={3} className="mt-1 w-full rounded-lg border border-slate-200 p-3 text-sm" data-testid="signup-profile" /></label>
        <label className="text-xs text-slate-600 sm:col-span-2">{t("password")} * (8+)<PasswordInput required minLength={8} value={f.password} onChange={set("password")} wrapperClassName="mt-1" className={inp} data-testid="signup-password" autoComplete="new-password" /></label>
        <Button type="submit" className="btn-emerald h-11 sm:col-span-2" disabled={busy} data-testid="signup-submit">{busy ? t("loading") : t("create_account")}</Button>
      </form>
    </Shell>
  );
}

export function InviteAccept() {
  const { t, user } = useApp();
  const { token } = useParams();
  const login = useAutoLogin();
  const { data, error } = useApi(`/public/invitations/${token}`, [token]);
  const [f, setF] = useState({ name: "", password: "" });
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;
  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    try { const r = await api.post(`/public/invitations/${token}/accept`, f); await login(r.data.email, f.password); } catch (err) { toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  const valid = data && data.status === "PENDING";
  return (
    <Shell title={t("accept_invite")} sub={data ? `${data.tenant_name} · ${t("invited_by")}: ${data.inviter}` : ""}>
      {!data && !error ? <div className="text-sm text-slate-400">{t("loading")}</div> : !valid ? <div className="text-sm text-red-600" data-testid="invite-invalid">{t("invite_invalid")}</div> : (
        <form onSubmit={submit} className="grid gap-3" data-testid="invite-accept-form">
          <div className="rounded-lg bg-slate-50 p-3 text-sm">{data.client_name} · <span className="font-num">{data.email}</span></div>
          <label className="text-xs text-slate-600">{t("name")}<input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className={inp} data-testid="invite-name" /></label>
          <label className="text-xs text-slate-600">{t("password")} (8+)<PasswordInput required minLength={8} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} wrapperClassName="mt-1" className={inp} data-testid="invite-password" autoComplete="new-password" /></label>
          <Button type="submit" className="btn-emerald h-11" disabled={busy} data-testid="invite-accept-submit">{t("accept_invite")}</Button>
        </form>
      )}
    </Shell>
  );
}
