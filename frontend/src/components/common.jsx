import { useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { useApp } from "@/context/AppContext";

export function PageHeader({ title, sub, eyebrow, children }) {
  return (
    <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between fade-up">
      <div>
        {eyebrow && <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-[#00A878]">{eyebrow}</div>}
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-[#071A2B] sm:text-4xl" data-testid="page-title">{title}</h1>
        {sub && <p className="mt-2 max-w-2xl text-sm text-slate-500">{sub}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Card({ className = "", children, ...p }) {
  return <div className={`glass-card rounded-2xl p-5 sm:p-6 ${className}`} {...p}>{children}</div>;
}

export function CardTitle({ children, right }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <h3 className="font-display text-[15px] font-bold tracking-tight text-[#071A2B]">{children}</h3>
      {right}
    </div>
  );
}

export function useCountUp(value, ms = 1100) {
  const [v, setV] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (value == null || isNaN(value)) return;
    const start = performance.now(), a = from.current;
    let raf;
    const step = (now) => {
      const p = Math.min(1, (now - start) / ms);
      const e = 1 - Math.pow(1 - p, 3);
      setV(a + (value - a) * e);
      if (p < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return v;
}

export function KpiCard({ label, value, format, sub, icon: Icon, accent = "emerald", testid, delay = 0 }) {
  const v = useCountUp(value);
  const ring = accent === "gold" ? "kpi-gold" : accent === "red" ? "kpi-red" : accent === "navy" ? "kpi-navy" : "kpi-emerald";
  return (
    <div className={`glass-card kpi ${ring} group rounded-2xl p-5 fade-up`} style={{ animationDelay: `${delay}ms` }} data-testid={testid}>
      <div className="flex items-start justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</span>
        {Icon && <Icon className="kpi-icon h-4 w-4" strokeWidth={1.8} />}
      </div>
      <div className="mt-3 font-num text-[22px] font-semibold tracking-tight text-[#071A2B] sm:text-2xl" data-testid={testid ? `${testid}-value` : undefined}>
        {format ? format(v) : Math.round(v)}
      </div>
      {sub && <div className="mt-1.5 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

const BADGE = {
  fact: "bg-slate-100 text-slate-700 border-slate-300",
  calc: "bg-sky-50 text-sky-700 border-sky-200",
  estimate: "bg-amber-50 text-amber-700 border-amber-200",
  ai: "bg-emerald-50 text-emerald-700 border-emerald-300",
};

export function AIBadge({ type }) {
  const { t } = useApp();
  return <span className={`inline-flex shrink-0 items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${BADGE[type] || BADGE.fact}`}>{t(type)}</span>;
}

const LEVEL = {
  ok: "bg-emerald-50 text-emerald-700 border-emerald-200",
  info: "bg-slate-50 text-slate-600 border-slate-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200",
  danger: "bg-red-50 text-red-700 border-red-200",
};

export function LevelBadge({ level, children }) {
  const { t } = useApp();
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${LEVEL[level] || LEVEL.info}`}>{children || t(level)}</span>;
}

export function AIThinking({ label }) {
  return (
    <div className="flex items-center gap-3 py-4" data-testid="ai-thinking">
      <div className="ai-orb"><Sparkles className="h-4 w-4 text-white" /></div>
      <div className="flex-1">
        <div className="text-sm font-medium text-[#071A2B]">{label}</div>
        <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-slate-100"><div className="ai-scan h-full w-1/3 rounded-full bg-gradient-to-r from-transparent via-[#00A878] to-transparent" /></div>
      </div>
    </div>
  );
}

export function Empty({ text }) {
  return <div className="py-10 text-center text-sm text-slate-400" data-testid="empty-state">{text}</div>;
}

export function Spinner() {
  return <div className="flex justify-center py-16"><div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00A878] border-t-transparent" /></div>;
}
