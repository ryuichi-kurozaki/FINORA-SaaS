import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowLeft, Lock, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";
import { LANGS } from "@/i18n/dict";
import { LogoFull, LogoMark } from "@/components/Logo";
import DemoLogins from "@/components/DemoLogins";
import { PasswordInput } from "@/components/PasswordInput";

const LETTERS = [["F", "Finance"], ["I", "Intelligence"], ["N", "Navigation"], ["O", "Optimization"], ["R", "Risk Management"], ["A", "Advisory"]];

export default function Login() {
  const { user, setUser, t, lang, setLang } = useApp();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState("");
  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const { data } = challenge ? await api.post("/auth/2fa/verify", { challenge_token: challenge, code }) : await api.post("/auth/login", { email, password });
      if (data.requires_2fa) { setChallenge(data.challenge_token); return; }
      localStorage.setItem("finora_token", data.access_token);
      const me = await api.get("/auth/me");
      if (me.data.lang && !localStorage.getItem("finora_lang")) setLang(me.data.lang);
      setUser(me.data);
      nav("/");
    } catch (e2) { setErr(errMsg(e2)); } finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.15fr_1fr]">
      <div className="login-bg relative hidden overflow-hidden p-12 text-white lg:flex lg:flex-col">
        <div className="grid-lines absolute inset-0" />
        <div className="relative"><Link to="/" data-testid="login-logo-home"><LogoFull dark className="h-28 w-auto" /></Link></div>
        <div className="relative mt-auto max-w-xl">
          <div className="mb-4 text-xs font-semibold uppercase tracking-[0.3em] text-[#00A878]">Investment Intelligence Platform</div>
          <h1 className="font-display text-5xl font-extrabold leading-[1.1] tracking-tight">Finance <span className="text-slate-500">×</span> Intelligence <span className="text-slate-500">×</span> <span className="text-[#00A878]">Future</span></h1>
          <p className="mt-5 text-base text-slate-300">{t("tagline")}</p>
          <div className="mt-10 grid grid-cols-3 gap-3">
            {LETTERS.map(([l, w], i) => (
              <div key={l} className="fade-up rounded-xl border border-white/10 bg-white/[0.04] p-3 backdrop-blur" style={{ animationDelay: `${i * 90}ms` }}>
                <div className={`font-display text-2xl font-extrabold ${i < 3 ? "text-white" : "text-[#00A878]"}`}>{l}</div>
                <div className="text-[11px] text-slate-400">{w}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="relative mt-10 text-[11px] text-slate-500">© FINORA · www.finora.co.jp</div>
      </div>
      <div className="flex flex-col items-center justify-center bg-[#F7F9FC] px-6 py-12">
        <div className="mb-8 flex w-full max-w-sm items-center justify-between">
          <Link to="/" className="hidden items-center gap-1 text-xs text-slate-500 hover:text-[#00A878] lg:inline-flex" data-testid="login-back-home"><ArrowLeft className="h-3.5 w-3.5" />{t("back_home")}</Link>
          <Link to="/" className="lg:hidden" data-testid="login-back-home-mobile"><LogoFull className="h-12 w-auto" /></Link>
          <div className="ml-auto flex rounded-xl border border-slate-200 bg-white p-0.5">
            {LANGS.map((l) => (
              <button key={l.code} onClick={() => setLang(l.code)} data-testid={`login-lang-${l.code}`}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${lang === l.code ? "bg-[#071A2B] text-white" : "text-slate-500"}`}>{l.short}</button>
            ))}
          </div>
        </div>
        <form onSubmit={submit} className="glass-card w-full max-w-sm rounded-2xl p-8 fade-up" data-testid="login-form">
          <LogoMark size={44} />
          <h2 className="mt-5 font-display text-2xl font-extrabold text-[#071A2B]">{t("welcome_back")}</h2>
          <p className="mt-1 text-sm text-slate-500">{t("login_sub")}</p>
          <label className="mt-7 block text-xs font-medium text-slate-600">{t("email")}</label>
          <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1.5 h-11" data-testid="login-email-input" autoComplete="username" />
          <label className="mt-4 block text-xs font-medium text-slate-600">{t("password")}</label>
          <PasswordInput required value={password} onChange={(e) => setPassword(e.target.value)} wrapperClassName="mt-1.5" className="h-11" data-testid="login-password-input" autoComplete="current-password" />
          {challenge && (
            <div className="mt-4 rounded-xl border border-[#00A878]/30 bg-emerald-50/50 p-3" data-testid="login-2fa-step">
              <label className="block text-xs font-medium text-slate-600">{t("twofa_prompt")}</label>
              <Input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoFocus className="mt-1.5 h-11 font-num tracking-[0.3em]" data-testid="login-2fa-code" />
            </div>
          )}
          {err && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" data-testid="login-error">{err}</div>}
          <Button type="submit" disabled={busy} className="btn-emerald mt-6 h-11 w-full text-sm font-semibold" data-testid="login-submit-button">
            <Lock className="mr-2 h-4 w-4" />{busy ? t("loading") : t("login")}
          </Button>
          <div className="mt-6 flex items-start gap-2 text-[11px] text-slate-500"><ShieldCheck className="h-4 w-4 shrink-0 text-[#00A878]" />{t("secure_note")}</div>
          <DemoLogins active={email} onPick={(e, p) => { setEmail(e); setPassword(p); setErr(""); }} />
          <Link to="/signup" className="mt-4 block text-center text-xs font-medium text-[#00A878] hover:underline" data-testid="login-signup-link">{t("no_account")}</Link>
        </form>
      </div>
    </div>
  );
}
