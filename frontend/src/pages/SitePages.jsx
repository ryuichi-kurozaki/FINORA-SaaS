import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, ChevronDown, MapPin } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { imgSrc, useSite } from "@/lib/useSite";
import { LandingFooter, LandingNav } from "@/components/landing/Chrome";
import ContactForm from "@/components/landing/ContactForm";
import { Spinner } from "@/components/common";

const CO_ROWS = ["company_name", "representative", "established", "capital", "address", "business", "employees", "phone", "email"];
const CATS = ["notice", "press", "media", "event"];

export function PublicShell({ eyebrow, title, children, testid }) {
  useEffect(() => { window.scrollTo(0, 0); }, []);
  return (
    <div className="min-h-screen bg-[#F7F9FC]" data-testid={testid}>
      <LandingNav />
      <section className="login-bg relative overflow-hidden px-5 pb-16 pt-32 text-white sm:px-8">
        <div className="grid-lines absolute inset-0" />
        <div className="relative mx-auto max-w-7xl fade-up">
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.28em] text-[#5FD4B0]">{eyebrow}</div>
          <h1 className="font-display text-4xl font-extrabold tracking-tight sm:text-5xl" data-testid="public-page-title">{title}</h1>
        </div>
      </section>
      <main className="mx-auto max-w-7xl px-5 py-16 sm:px-8">{children}</main>
      <LandingFooter />
    </div>
  );
}

const H2 = ({ children }) => <h2 className="mb-6 border-l-4 border-[#00A878] pl-4 font-display text-2xl font-bold text-[#071A2B]">{children}</h2>;
const DateTag = ({ d }) => <span className="font-num text-xs text-slate-500">{(d || "").replaceAll("-", ".")}</span>;
const CatTag = ({ c, t }) => c ? <span className="rounded-full bg-[#00A878]/10 px-2.5 py-0.5 text-[11px] font-semibold text-[#0B6E4F]">{t(`news_cat_${c}`)}</span> : null;

export function Company() {
  const { t } = useApp();
  const s = useSite();
  if (!s) return <PublicShell eyebrow="Company" title={t("nav_company")}><Spinner /></PublicShell>;
  const st = s.settings;
  return (
    <PublicShell eyebrow="Company" title={t("nav_company")} testid="company-page">
      <section className="mb-20 grid items-center gap-10 lg:grid-cols-[1fr_1.4fr]" data-testid="company-message">
        {st.message_image ? <img src={imgSrc(st.message_image)} alt="" className="aspect-[4/5] w-full rounded-2xl object-cover shadow-xl" /> : <div className="aspect-[4/5] w-full rounded-2xl bg-gradient-to-br from-[#071A2B] to-[#0B6E4F]" />}
        <div><div className="mb-2 text-xs font-semibold uppercase tracking-[0.25em] text-[#00A878]">{t("co_message")}</div>
          <h2 className="font-display text-3xl font-extrabold text-[#071A2B]">{st.message_title}</h2>
          <p className="mt-6 whitespace-pre-line leading-8 text-slate-600">{st.message_body}</p>
          <p className="mt-6 text-right font-display font-semibold text-[#071A2B]">{st.message_signature}</p></div>
      </section>
      <section className="mb-20" data-testid="company-overview"><H2>{t("co_overview")}</H2>
        <dl className="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          {CO_ROWS.filter((k) => st[k]).map((k) => <div key={k} className="grid gap-1 px-6 py-4 sm:grid-cols-[200px_1fr]"><dt className="text-sm font-semibold text-slate-500">{t(`co_${k}`)}</dt><dd className="whitespace-pre-line text-sm text-slate-800">{st[k]}</dd></div>)}
        </dl></section>
      {s.history.length > 0 && <section className="mb-20" data-testid="company-history"><H2>{t("co_history")}</H2>
        <ol className="relative space-y-6 border-l-2 border-[#00A878]/30 pl-8">
          {s.history.map((h) => <li key={h.id} className="relative"><span className="absolute -left-[41px] top-1 h-4 w-4 rounded-full border-4 border-white bg-[#00A878]" />
            <div className="font-num text-sm font-semibold text-[#0B6E4F]">{h.date}</div><div className="font-medium text-slate-800">{h.title}</div>{h.body && <p className="text-sm text-slate-500">{h.body}</p>}</li>)}
        </ol></section>}
      <section data-testid="company-access"><H2>{t("co_access")}</H2>
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex items-start gap-3"><MapPin className="mt-0.5 h-5 w-5 text-[#00A878]" /><div><div className="text-sm text-slate-800">{st.address}</div><div className="text-sm text-slate-500">{st.access_note}</div></div></div>
          {st.map_url && <a href={st.map_url} target="_blank" rel="noreferrer" className="btn-emerald rounded-full px-5 py-2 text-sm font-semibold" data-testid="company-map-link">{t("co_map")}</a>}
        </div></section>
    </PublicShell>
  );
}

export function Services() {
  const { t } = useApp();
  const s = useSite();
  return (
    <PublicShell eyebrow="Services" title={t("nav_services")} testid="services-page">
      {!s ? <Spinner /> : <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {s.services.map((v, i) => <article key={v.id} className="group overflow-hidden rounded-2xl border border-slate-200 bg-white transition-transform hover:-translate-y-1 hover:shadow-xl" data-testid={`service-card-${i}`}>
          {v.image ? <img src={imgSrc(v.image)} alt="" className="aspect-[16/9] w-full object-cover" /> : <div className="flex aspect-[16/9] items-end bg-gradient-to-br from-[#071A2B] to-[#0B6E4F] p-5 font-num text-5xl font-bold text-white/20">{String(i + 1).padStart(2, "0")}</div>}
          <div className="p-6"><h3 className="font-display text-lg font-bold text-[#071A2B]">{v.title}</h3><p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-600">{v.body}</p></div>
        </article>)}
      </div>}
      <div className="mt-14 text-center"><Link to="/contact" className="btn-emerald inline-flex items-center gap-2 rounded-full px-7 py-3 text-sm font-semibold">{t("nav_contact")}<ArrowRight className="h-4 w-4" /></Link></div>
    </PublicShell>
  );
}

export function NewsRow({ n, t }) {
  return (
    <Link to={`/news/${n.id}`} className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-slate-200 px-2 py-5 transition-colors hover:bg-white" data-testid={`news-row-${n.id}`}>
      <DateTag d={n.date} /><CatTag c={n.category} t={t} /><span className="flex-1 text-sm font-medium text-slate-800">{n.title}</span><ArrowRight className="h-4 w-4 text-slate-300" />
    </Link>
  );
}

export function NewsList() {
  const { t, lang } = useApp();
  const [cat, setCat] = useState("");
  const { data } = useApi(`/public/site/news?lang=${lang}${cat ? `&category=${cat}` : ""}`, [lang, cat]);
  return (
    <PublicShell eyebrow="News" title={t("nav_news")} testid="news-page">
      <div className="mb-8 flex flex-wrap gap-2">{["", ...CATS].map((c) => <button key={c || "all"} onClick={() => setCat(c)} data-testid={`news-filter-${c || "all"}`}
        className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-colors ${cat === c ? "bg-[#071A2B] text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>{c ? t(`news_cat_${c}`) : t("news_all")}</button>)}</div>
      {!data ? <Spinner /> : data.length ? <div>{data.map((n) => <NewsRow key={n.id} n={n} t={t} />)}</div> : <p className="text-sm text-slate-400">—</p>}
    </PublicShell>
  );
}

export function NewsDetail() {
  const { t, lang } = useApp();
  const { id } = useParams();
  const { data, loading } = useApi(`/public/site/news/${id}?lang=${lang}`, [id, lang]);
  return (
    <PublicShell eyebrow="News" title={t("nav_news")} testid="news-detail-page">
      {loading ? <Spinner /> : !data ? <p className="text-sm text-slate-500" data-testid="news-not-found">404</p> : <article className="mx-auto max-w-3xl">
        <div className="flex items-center gap-3"><DateTag d={data.date} /><CatTag c={data.category} t={t} /></div>
        <h2 className="mt-3 font-display text-3xl font-bold text-[#071A2B]" data-testid="news-detail-title">{data.title}</h2>
        {data.image && <img src={imgSrc(data.image)} alt="" className="mt-8 w-full rounded-2xl object-cover" />}
        <div className="mt-8 whitespace-pre-line leading-8 text-slate-700">{data.body}</div>
        <Link to="/news" className="mt-12 inline-block text-sm font-semibold text-[#0B6E4F]" data-testid="news-back">← {t("news_back")}</Link>
      </article>}
    </PublicShell>
  );
}

export function Faq() {
  const { t } = useApp();
  const s = useSite();
  return (
    <PublicShell eyebrow="FAQ" title={t("nav_faq")} testid="faq-page">
      {!s ? <Spinner /> : <div className="mx-auto max-w-3xl space-y-3">{s.faqs.map((f, i) => (
        <details key={f.id} className="group rounded-2xl border border-slate-200 bg-white p-5" data-testid={`faq-item-${i}`}>
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-[#071A2B]"><span><span className="mr-3 font-display text-[#00A878]">Q.</span>{f.title}</span><ChevronDown className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180" /></summary>
          <p className="mt-4 whitespace-pre-line border-t border-slate-100 pt-4 text-sm leading-7 text-slate-600"><span className="mr-3 font-display font-bold text-[#C9A227]">A.</span>{f.body}</p>
        </details>))}</div>}
    </PublicShell>
  );
}

export function Contact() {
  const { t } = useApp();
  return (
    <PublicShell eyebrow="Contact" title={t("nav_contact")} testid="contact-page">
      <p className="mx-auto mb-10 max-w-3xl text-slate-500">{t("contact_sub")}</p>
      <div className="mx-auto max-w-3xl"><ContactForm /></div>
    </PublicShell>
  );
}
