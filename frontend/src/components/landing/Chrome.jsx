import { useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { LANGS } from "@/i18n/dict";
import { Logo, LogoFull } from "@/components/Logo";

const LINKS = [["nav_features", "#features"], ["nav_security", "#security"], ["nav_pricing", "#pricing"], ["nav_contact", "#contact"]];

export function LangSwitch({ dark }) {
  const { lang, setLang } = useApp();
  return (
    <div className={`flex rounded-full border p-0.5 ${dark ? "border-white/15 bg-white/5" : "border-slate-200 bg-white"}`}>
      {LANGS.map((l) => (
        <button key={l.code} onClick={() => setLang(l.code)} data-testid={`landing-lang-${l.code}`}
          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors ${lang === l.code ? "bg-[#00A878] text-white" : dark ? "text-slate-300 hover:text-white" : "text-slate-500"}`}>{l.short}</button>
      ))}
    </div>
  );
}

export function LandingNav() {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-white/5 bg-[#071A2B]/92 backdrop-blur-xl" data-testid="landing-nav">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-5 sm:px-8">
        <Link to="/" data-testid="landing-logo-link"><Logo light size={34} /></Link>
        <nav className="ml-6 hidden items-center gap-7 md:flex">
          {LINKS.map(([k, h]) => <a key={k} href={h} className="text-sm text-slate-300 transition-colors hover:text-white" data-testid={`landing-link-${k}`}>{t(k)}</a>)}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <div className="hidden sm:block"><LangSwitch dark /></div>
          <Link to="/signup" className="hidden rounded-full border border-white/30 px-4 py-2 text-sm text-white hover:border-[#00A878] sm:inline-flex" data-testid="landing-signup-btn">{t("signup")}</Link>
          <Link to="/login" className="btn-emerald rounded-full px-5 py-2 text-sm font-semibold" data-testid="landing-login-btn">{t("cta_login")}</Link>
          <button className="text-white md:hidden" onClick={() => setOpen(!open)} data-testid="landing-menu-btn">{open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
        </div>
      </div>
      {open && (
        <div className="space-y-3 border-t border-white/5 px-5 py-4 md:hidden">
          {LINKS.map(([k, h]) => <a key={k} href={h} onClick={() => setOpen(false)} className="block text-sm text-slate-200">{t(k)}</a>)}
          <LangSwitch dark />
        </div>
      )}
    </header>
  );
}

export function LandingFooter() {
  const { t } = useApp();
  return (
    <footer className="bg-[#071A2B] text-slate-400" data-testid="landing-footer">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 md:grid-cols-[1.5fr_1fr_1fr]">
        <div><LogoFull dark className="h-20 w-auto" /><p className="mt-5 max-w-sm text-sm">{t("tagline")}</p></div>
        <div className="space-y-2.5 text-sm">
          {LINKS.map(([k, h]) => <a key={k} href={h} className="block hover:text-white">{t(k)}</a>)}
        </div>
        <div className="space-y-2.5 text-sm">
          <Link to="/legal" className="block hover:text-white" data-testid="footer-terms">{t("terms")}</Link>
          <Link to="/legal#privacy" className="block hover:text-white" data-testid="footer-privacy">{t("privacy")}</Link>
          <Link to="/login" className="block hover:text-white">{t("cta_login")}</Link>
          <div className="pt-2"><LangSwitch dark /></div>
        </div>
      </div>
      <div className="border-t border-white/5 py-6 text-center text-xs">© {new Date().getFullYear()} FINORA · www.finora.co.jp · {t("rights")}</div>
    </footer>
  );
}
