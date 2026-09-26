import { ArrowRight, Brain, Briefcase, Building2, Check, FileBarChart, Fingerprint, KeyRound, LayoutDashboard, Lock, Network, ScrollText, ShieldAlert, ShieldCheck, Telescope, UserRound, Users } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { AIBadge } from "@/components/common";
import HeroPreview from "@/components/landing/HeroPreview";
import ContactForm from "@/components/landing/ContactForm";
import { LandingFooter, LandingNav } from "@/components/landing/Chrome";
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useSite } from "@/lib/useSite";
import { NewsRow } from "@/pages/SitePages";

const LETTERS = [["F", "Finance"], ["I", "Intelligence"], ["N", "Navigation"], ["O", "Optimization"], ["R", "Risk Management"], ["A", "Advisory"]];
const FLOW = ["clients", "accounts", "assets", "cashflow", "portfolio", "analytics", "risk", "simulation", "ai_insight", "consulting", "reports"];
const FEATS = [["f1", LayoutDashboard, "lg:col-span-2"], ["f2", Brain, "lg:row-span-2"], ["f3", ShieldAlert, ""], ["f4", Telescope, ""], ["f5", FileBarChart, ""], ["f6", Briefcase, "lg:col-span-2"]];
const WHO = [["who1", UserRound], ["who2", Building2], ["who3", Users]];
const SEC = [["s1", Lock], ["s2", KeyRound], ["s3", ScrollText], ["s4", Fingerprint], ["s5", ShieldCheck], ["s6", Network]];
const MEETING_IMG = "https://images.pexels.com/photos/5816285/pexels-photo-5816285.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

function Section({ id, eyebrow, title, sub, dark, children, className = "" }) {
  return (
    <section id={id} className={`scroll-mt-16 px-5 py-24 sm:px-8 ${dark ? "bg-[#071A2B] text-white" : ""} ${className}`}>
      <div className="mx-auto max-w-7xl">
        {eyebrow && <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.28em] text-[#00A878]">{eyebrow}</div>}
        {title && <h2 className={`max-w-3xl font-display text-3xl font-extrabold tracking-tight sm:text-4xl ${dark ? "text-white" : "text-[#071A2B]"}`}>{title}</h2>}
        {sub && <p className={`mt-4 max-w-2xl text-base ${dark ? "text-slate-400" : "text-slate-500"}`}>{sub}</p>}
        <div className="mt-14">{children}</div>
      </div>
    </section>
  );
}

function Hero() {
  const { t } = useApp();
  return (
    <section className="login-bg relative overflow-hidden px-5 pb-28 pt-36 text-white sm:px-8" data-testid="landing-hero">
      <div className="grid-lines absolute inset-0" />
      <div className="relative mx-auto grid max-w-7xl items-center gap-16 lg:grid-cols-[1.1fr_1fr]">
        <div className="fade-up">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[#00A878]/30 bg-[#00A878]/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[#5FD4B0]">{t("hero_eyebrow")}</div>
          <h1 className="font-display text-4xl font-extrabold leading-[1.15] tracking-tight sm:text-5xl lg:text-6xl" data-testid="landing-hero-title">{t("tagline")}</h1>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-slate-300 sm:text-lg">{t("hero_sub")}</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <a href="#contact" className="btn-emerald inline-flex items-center gap-2 rounded-full px-7 py-3.5 text-sm font-semibold" data-testid="hero-contact-btn">{t("cta_contact")}<ArrowRight className="h-4 w-4" /></a>
            <a href="#features" className="inline-flex items-center rounded-full border border-white/20 px-7 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-white/10" data-testid="hero-features-btn">{t("cta_features")}</a>
          </div>
          <div className="mt-12 flex gap-10">
            {[["16", "hero_stat1"], ["8", "hero_stat2"], ["3", "hero_stat3"]].map(([n, k]) => (
              <div key={k}><div className="font-num text-3xl font-semibold text-[#C9A227]">{n}</div><div className="mt-1 text-xs text-slate-400">{t(k)}</div></div>
            ))}
          </div>
        </div>
        <div className="fade-up" style={{ animationDelay: "200ms" }}><HeroPreview /></div>
      </div>
    </section>
  );
}

function Brand() {
  const { t } = useApp();
  return (
    <Section eyebrow="Brand" title={t("brand_title")} sub={t("brand_sub")}>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        {LETTERS.map(([l, w], i) => (
          <div key={l} className="glass-card group rounded-2xl p-6 hover:-translate-y-1" data-testid={`brand-letter-${l}`}>
            <div className={`font-display text-5xl font-extrabold ${i < 3 ? "text-[#071A2B]" : "text-[#00A878]"}`}>{l}</div>
            <div className="mt-4 text-sm font-semibold text-[#071A2B]">{w}</div>
            <div className="mt-1 text-xs leading-relaxed text-slate-500">{t(`${l}_desc`)}</div>
          </div>
        ))}
      </div>
      <div className="mt-16 rounded-3xl border border-slate-200 bg-white p-8">
        <h3 className="font-display text-xl font-bold text-[#071A2B]">{t("flow_title")}</h3>
        <p className="mt-2 text-sm text-slate-500">{t("flow_sub")}</p>
        <div className="mt-6 flex flex-wrap items-center gap-2 text-xs">
          {FLOW.map((k, i) => <span key={k} className="flex items-center gap-2"><span className="rounded-full bg-[#071A2B] px-3 py-1.5 text-white">{t(k)}</span>{i < FLOW.length - 1 && <ArrowRight className="h-3.5 w-3.5 text-[#00A878]" />}</span>)}
        </div>
      </div>
    </Section>
  );
}

function Features() {
  const { t } = useApp();
  return (
    <Section id="features" eyebrow="Features" title={t("feat_title")} sub={t("feat_sub")} className="bg-white">
      <div className="grid gap-5 lg:grid-cols-3">
        {FEATS.map(([k, Icon, span]) => (
          <div key={k} className={`group relative overflow-hidden rounded-3xl border border-slate-200 p-8 transition-colors hover:border-[#00A878]/50 ${span} ${k === "f2" ? "ai-panel text-white" : "bg-[#F7F9FC]"}`} data-testid={`feature-${k}`}>
            {k === "f2" && <div className="ai-glow" />}
            <div className={`relative flex h-12 w-12 items-center justify-center rounded-2xl ${k === "f2" ? "ai-orb" : "bg-white text-[#00A878] shadow-sm"}`}><Icon className={`h-5 w-5 ${k === "f2" ? "text-white" : ""}`} strokeWidth={1.7} /></div>
            <h3 className={`relative mt-6 font-display text-xl font-bold ${k === "f2" ? "text-white" : "text-[#071A2B]"}`}>{t(`${k}_t`)}</h3>
            <p className={`relative mt-3 text-sm leading-relaxed ${k === "f2" ? "text-slate-300" : "text-slate-500"}`}>{t(`${k}_d`)}</p>
            {k === "f2" && <div className="relative mt-8 space-y-2">{["ai_s1", "ai_s2", "ai_s3"].map((s) => <div key={s} className="rounded-xl bg-white/[0.06] px-3 py-2 text-xs text-slate-200">{t(s)}</div>)}</div>}
          </div>
        ))}
      </div>
    </Section>
  );
}

function AIShowcase() {
  const { t } = useApp();
  const rows = [["fact", "ai_s1"], ["calc", "ai_s2"], ["estimate", "ai_s3"], ["ai", "ai_s4"]];
  return (
    <Section eyebrow="AI Intelligence" title={t("landing_ai_title")} sub={t("ai_sub")}>
      <div className="grid items-center gap-10 lg:grid-cols-2">
        <div className="space-y-3">
          {rows.map(([type, k], i) => (
            <div key={k} className="glass-card flex items-start gap-3 rounded-2xl p-4 fade-up" style={{ animationDelay: `${i * 120}ms` }} data-testid={`ai-sample-${type}`}>
              <AIBadge type={type} /><span className="text-sm text-slate-700">{t(k)}</span>
            </div>
          ))}
        </div>
        <div className="overflow-hidden rounded-3xl">
          <img src={MEETING_IMG} alt="Advisory meeting" className="h-[360px] w-full object-cover" loading="lazy" />
        </div>
      </div>
    </Section>
  );
}

function Who() {
  const { t } = useApp();
  return (
    <Section eyebrow="For" title={t("who_title")} className="bg-white">
      <div className="grid gap-5 md:grid-cols-3">
        {WHO.map(([k, Icon]) => (
          <div key={k} className="rounded-3xl border border-slate-200 p-8" data-testid={`who-${k}`}>
            <Icon className="h-7 w-7 text-[#C9A227]" strokeWidth={1.6} />
            <h3 className="mt-5 font-display text-lg font-bold text-[#071A2B]">{t(`${k}_t`)}</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">{t(`${k}_d`)}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Security() {
  const { t } = useApp();
  return (
    <Section id="security" eyebrow="Security" title={t("sec_title")} sub={t("sec_sub")} dark className="relative overflow-hidden">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SEC.map(([k, Icon]) => (
          <div key={k} className="flex items-center gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-5 transition-colors hover:border-[#00A878]/40" data-testid={`security-${k}`}>
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#00A878]/15"><Icon className="h-5 w-5 text-[#00A878]" strokeWidth={1.7} /></div>
            <span className="text-sm text-slate-200">{t(k)}</span>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Pricing() {
  const { t } = useApp();
  const plans = [["Starter", "pl1"], ["Professional", "pl2"], ["Enterprise", "pl3"]];
  return (
    <Section id="pricing" eyebrow="Pricing" title={t("price_title")} sub={t("price_sub")}>
      <div className="grid gap-5 lg:grid-cols-3">
        {plans.map(([name, k]) => {
          const pro = k === "pl2";
          return (
            <div key={k} className={`relative rounded-3xl p-8 ${pro ? "bg-[#071A2B] text-white shadow-2xl ring-1 ring-[#C9A227]/50 lg:-translate-y-3" : "glass-card"}`} data-testid={`plan-${k}`}>
              {pro && <span className="absolute right-6 top-6 rounded-full bg-[#C9A227] px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-[#071A2B]">{t("popular")}</span>}
              <div className={`font-display text-2xl font-extrabold ${pro ? "text-white" : "text-[#071A2B]"}`}>{name}</div>
              <div className={`mt-1 text-sm ${pro ? "text-slate-400" : "text-slate-500"}`}>{t(`${k}_d`)}</div>
              <div className={`mt-6 font-display text-2xl font-bold ${pro ? "text-[#C9A227]" : "text-[#071A2B]"}`}>{t("price_contact")}</div>
              <ul className="mt-6 space-y-3">{[1, 2, 3, 4].map((n) => <li key={n} className={`flex items-center gap-2.5 text-sm ${pro ? "text-slate-200" : "text-slate-600"}`}><Check className="h-4 w-4 shrink-0 text-[#00A878]" />{t(`${k}_f${n}`)}</li>)}</ul>
              <a href="#contact" className={`mt-8 block rounded-full py-3 text-center text-sm font-semibold transition-colors ${pro ? "btn-emerald" : "border border-slate-300 text-[#071A2B] hover:border-[#00A878] hover:text-[#00A878]"}`} data-testid={`plan-${k}-cta`}>{t("choose")}</a>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

function LatestNews() {
  const { t } = useApp();
  const s = useSite();
  if (!s) return null;
  return (
    <Section id="news" eyebrow="News" title={t("news_latest")} className="bg-white">
      <div className="grid gap-10 lg:grid-cols-[1.6fr_1fr]">
        <div data-testid="landing-news">{s.news.map((n) => <NewsRow key={n.id} n={n} t={t} />)}
          <Link to="/news" className="mt-6 inline-flex items-center gap-1 text-sm font-semibold text-[#0B6E4F]" data-testid="landing-news-more">{t("news_more")}<ArrowRight className="h-4 w-4" /></Link></div>
        <Link to="/company" className="group relative overflow-hidden rounded-2xl bg-[#071A2B] p-8 text-white" data-testid="landing-company-card">
          <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#5FD4B0]">Company</div>
          <div className="mt-3 font-display text-2xl font-bold">{s.settings.message_title}</div>
          <div className="mt-2 text-sm text-slate-400">{s.settings.company_name}</div>
          <div className="mt-8 inline-flex items-center gap-1 text-sm font-semibold text-[#5FD4B0]">{t("nav_company")}<ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></div>
        </Link>
      </div>
    </Section>
  );
}

function useHashScroll() {
  const { hash, key } = useLocation();
  useEffect(() => {
    if (!hash) { window.scrollTo({ top: 0, behavior: "smooth" }); return undefined; }
    let tries = 0;
    const id = setInterval(() => {
      const el = document.getElementById(hash.slice(1));
      if (el || ++tries > 40) clearInterval(id);
      if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 72, behavior: "smooth" });
    }, 50);
    return () => clearInterval(id);
  }, [hash, key]);
}

export default function Landing() {
  const { t } = useApp();
  useHashScroll();
  return (
    <div className="min-h-screen bg-[#F7F9FC]" data-testid="landing-page">
      <LandingNav />
      <Hero />
      <Brand />
      <Features />
      <AIShowcase />
      <Who />
      <Security />
      <Pricing />
      <LatestNews />
      <Section id="contact" eyebrow="Contact" title={t("contact_title")} sub={t("contact_sub")} className="bg-white">
        <div className="mx-auto max-w-3xl"><ContactForm /></div>
      </Section>
      <LandingFooter />
    </div>
  );
}
