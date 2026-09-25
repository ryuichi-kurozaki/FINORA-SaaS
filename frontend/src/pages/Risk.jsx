import { ShieldAlert } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { useDashboard, useScopeLabel } from "@/lib/useDashboard";
import { Card, CardTitle, LevelBadge, PageHeader, Spinner, useCountUp } from "@/components/common";
import { InsightItems } from "@/components/InsightPanel";

const NAME = { concentration: "concentration", currency: "currency_risk", country: "country_risk", sector: "sector_risk", interest_rate: "interest_rate_risk", liquidity: "liquidity", leverage: "leverage", balance: "balance_risk" };
const BAR = { ok: "#00A878", warn: "#C9A227", danger: "#DC2626" };

function Score({ score }) {
  const { t } = useApp();
  const v = useCountUp(score);
  const color = score >= 75 ? "#00A878" : score >= 50 ? "#C9A227" : "#DC2626";
  return (
    <div className="relative mx-auto h-44 w-44" data-testid="risk-score">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r="42" stroke="#EDF2F7" strokeWidth="8" fill="none" />
        <circle cx="50" cy="50" r="42" stroke={color} strokeWidth="8" fill="none" strokeLinecap="round" strokeDasharray={`${(v / 100) * 264} 264`} style={{ filter: `drop-shadow(0 0 6px ${color}66)` }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-num text-4xl font-semibold text-[#071A2B]" data-testid="risk-score-value">{Math.round(v)}</span>
        <span className="text-[11px] text-slate-500">{t("risk_score")}</span>
      </div>
    </div>
  );
}

export default function Risk() {
  const { t } = useApp();
  const { data } = useDashboard();
  const scope = useScopeLabel();
  if (!data) return <Spinner />;
  const r = data.risk;
  const unit = (i) => (i.unit === "months" ? t("months_short") : i.unit === "x" ? "x" : "%");
  return (
    <div data-testid="risk-page">
      <PageHeader eyebrow={`Risk · ${scope}`} title={t("risk")} />
      <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
        <Card className="flex flex-col items-center justify-center">
          <Score score={r.score} />
          <div className="mt-5 w-full"><div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#071A2B]"><ShieldAlert className="h-4 w-4 text-red-500" />{t("risk_alerts")}</div><InsightItems items={data.insights.risks} /></div>
        </Card>
        <div className="grid gap-4 sm:grid-cols-2">
          {r.items.map((i) => {
            const max = i.reverse ? Math.max(i.warn * 2, 1) : Math.max(i.danger * 1.4, i.value);
            const w = Math.min(100, (Math.min(i.value, max) / max) * 100);
            return (
              <div key={i.code} className="glass-card rounded-2xl p-5" data-testid={`risk-item-${i.code}`}>
                <div className="flex items-center justify-between"><span className="text-sm font-semibold text-[#071A2B]">{t(NAME[i.code])}</span><LevelBadge level={i.level} /></div>
                <div className="mt-3 font-num text-2xl font-semibold text-[#071A2B]">{i.value >= 99 ? "—" : i.value}<span className="ml-1 text-sm text-slate-500">{unit(i)}</span></div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full transition-[width] duration-1000" style={{ width: `${w}%`, background: BAR[i.level] }} /></div>
                <div className="mt-2 text-[11px] text-slate-500">{t("threshold")}: {t("warn")} {i.reverse ? "<" : ">"} {i.warn}{unit(i)} · {t("danger")} {i.reverse ? "<" : ">"} {i.danger}{unit(i)}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
