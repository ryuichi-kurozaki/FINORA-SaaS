import { AlertTriangle, ClipboardCheck, DatabaseZap, History, Sparkles, TrendingUp } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { AIBadge } from "@/components/common";

const DOT = { ok: "bg-[#00A878]", info: "bg-slate-400", warn: "bg-[#C9A227]", danger: "bg-red-500" };
const GROUPS = [["summary", "ai_summary", Sparkles], ["changes", "important_changes", TrendingUp], ["risks", "risks_to_watch", AlertTriangle],
  ["checks", "items_to_check", ClipboardCheck], ["since_last", "since_last_meeting", History], ["missing", "missing_data", DatabaseZap]];

export function InsightItems({ items }) {
  const { t } = useApp();
  if (!items?.length) return <div className="text-xs text-slate-400">{t("no_data")}</div>;
  return (
    <ul className="space-y-2.5">
      {items.map((it, i) => (
        <li key={i} className="flex items-start gap-2.5 text-[13px] leading-relaxed text-slate-700">
          <span className={`mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full ${DOT[it.severity] || DOT.info}`} />
          <span className="flex-1">{it.text}</span>
          <AIBadge type={it.type} />
        </li>
      ))}
    </ul>
  );
}

export default function InsightPanel({ insights, groups = GROUPS.map((g) => g[0]) }) {
  const { t } = useApp();
  return (
    <section className="ai-panel relative overflow-hidden rounded-2xl p-6 sm:p-7" data-testid="ai-insight-panel">
      <div className="ai-glow" />
      <div className="relative mb-6 flex flex-wrap items-center gap-3">
        <div className="ai-orb"><Sparkles className="h-4 w-4 text-white" /></div>
        <div>
          <h2 className="font-display text-lg font-extrabold tracking-[0.12em] text-white">{t("ai_title")}</h2>
          <p className="text-[11px] text-slate-400">{t("ai_engine_note")}</p>
        </div>
      </div>
      <div className="relative grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {GROUPS.filter((g) => groups.includes(g[0])).map(([k, label, Icon]) => (
          <div key={k} className={`rounded-xl bg-white p-4 shadow-sm ${k === "summary" ? "ring-1 ring-[#00A878]/40" : ""}`} data-testid={`ai-insight-${k}`}>
            <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.12em] text-[#071A2B]">
              <Icon className={`h-4 w-4 ${k === "risks" ? "text-red-500" : k === "summary" ? "text-[#00A878]" : "text-[#C9A227]"}`} />{t(label)}
            </div>
            <InsightItems items={insights?.[k]} />
          </div>
        ))}
      </div>
    </section>
  );
}
