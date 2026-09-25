import { Target } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { compact } from "@/lib/format";
import { Card, CardTitle, Empty, AIBadge } from "@/components/common";

const fmtV = (g, v, lang) => (["debt_ratio"].includes(g.category) ? `${Number(v).toFixed(1)}%` : compact(v, lang));

export default function GoalsPanel({ goals, title }) {
  const { t, lang } = useApp();
  return (
    <Card data-testid="goals-panel">
      <CardTitle>{title || t("goals_progress")}</CardTitle>
      {!goals?.length ? <Empty text={t("no_data")} /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {goals.map((g) => (
            <div key={g.id} className="rounded-xl border border-slate-100 bg-white p-4" data-testid={`goal-card-${g.id}`}>
              <div className="flex items-start gap-2">
                <Target className="mt-0.5 h-4 w-4 shrink-0 text-[#C9A227]" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold text-[#071A2B]">{g.name}</div>
                  <div className="text-[11px] text-slate-500">{t(`g_${g.category}`)} · {g.target_date || "—"}{g.months_left != null && ` · ${g.months_left}${lang === "ja" ? "ヶ月" : "m"}`}</div>
                </div>
                <span className="font-num text-lg font-bold text-[#00A878]" data-testid={`goal-progress-${g.id}`}>{g.progress_pct.toFixed(0)}%</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-[#00A878] to-[#5FD4B0] transition-all duration-700" style={{ width: `${g.progress_pct}%` }} /></div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
                <div><div className="text-slate-400">{t("current")}</div><div className="font-num text-slate-700">{fmtV(g, g.current, lang)} <span className="text-slate-400">({t(g.current_source === "auto" ? "auto_value" : "manual_value")})</span></div></div>
                <div><div className="text-slate-400">{t("target_amount")}</div><div className="font-num text-slate-700">{fmtV(g, g.target_amount, lang)}</div></div>
                <div><div className="text-slate-400">{t("remaining")}</div><div className="font-num text-slate-700">{fmtV(g, g.remaining, lang)}</div></div>
              </div>
              {g.simulation && (
                <div className="mt-3 rounded-lg bg-amber-50/60 p-2.5">
                  <div className="mb-1 flex items-center gap-2"><AIBadge type="simulation" /><span className="text-[10px] text-slate-500">{g.simulation.year}{lang === "ja" ? "年後" : "y"}</span></div>
                  <div className="grid grid-cols-3 gap-1 text-[11px]">
                    {["bull", "base", "bear"].map((s) => (
                      <div key={s}><span className="text-slate-500">{t(s)}</span> <span className={g.simulation[s].reached ? "font-semibold text-[#00A878]" : "text-slate-500"}>{t(g.simulation[s].reached ? "reached" : "not_reached")}</span></div>
                    ))}
                  </div>
                  <div className="mt-1 text-[10px] text-slate-500">{t("sim_note")}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
