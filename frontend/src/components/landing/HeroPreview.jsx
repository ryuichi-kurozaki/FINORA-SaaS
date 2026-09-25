import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { Sparkles, TrendingUp } from "lucide-react";
import { useApp } from "@/context/AppContext";

const SERIES = Array.from({ length: 24 }, (_, i) => ({ v: 80 + i * 1.6 + Math.sin(i / 2) * 4 - (i > 8 && i < 12 ? 6 : 0) }));
const ALLOC = [["#00A878", 63], ["#5FD4B0", 16], ["#C9A227", 9], ["#1F6F8B", 7], ["#8CA3B8", 5]];

export default function HeroPreview() {
  const { t } = useApp();
  return (
    <div className="relative" data-testid="hero-preview">
      <div className="absolute -inset-2 rounded-[40px] bg-[#00A878]/20 blur-3xl sm:-inset-8" />
      <div className="relative rounded-3xl border border-white/10 bg-white/[0.06] p-5 shadow-2xl backdrop-blur-xl">
        <div className="mb-4 flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-white/20" /><span className="h-2.5 w-2.5 rounded-full bg-white/20" /><span className="h-2.5 w-2.5 rounded-full bg-white/20" /></div>
        <div className="grid grid-cols-3 gap-3">
          {[["total_assets", "¥12.48億", "#00A878"], ["net_worth", "¥6.36億", "#C9A227"], ["yield", "+17.2%", "#5FD4B0"]].map(([k, v, c]) => (
            <div key={k} className="rounded-xl border border-white/10 bg-[#071A2B]/60 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-400">{t(k)}</div>
              <div className="mt-1 whitespace-nowrap font-num text-[13px] font-semibold sm:text-base" style={{ color: c }}>{v}</div>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-[1.6fr_1fr] gap-3">
          <div className="rounded-xl border border-white/10 bg-[#071A2B]/60 p-3">
            <div className="flex items-center gap-1.5 text-[11px] text-slate-300"><TrendingUp className="h-3.5 w-3.5 text-[#00A878]" />{t("asset_trend")}</div>
            <div className="h-28">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={SERIES}>
                  <defs><linearGradient id="hp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#00A878" stopOpacity={0.5} /><stop offset="1" stopColor="#00A878" stopOpacity={0} /></linearGradient></defs>
                  <Area type="monotone" dataKey="v" stroke="#00A878" strokeWidth={2} fill="url(#hp)" animationDuration={1800} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="rounded-xl border border-white/10 bg-[#071A2B]/60 p-3">
            <div className="text-[11px] text-slate-300">{t("allocation")}</div>
            <div className="mt-3 flex h-3 overflow-hidden rounded-full">{ALLOC.map(([c, w]) => <span key={c} style={{ width: `${w}%`, background: c }} />)}</div>
            <ul className="mt-3 space-y-1">{["real_estate", "deposit", "foreign_stock"].map((k, i) => <li key={k} className="flex items-center gap-1.5 text-[10px] text-slate-400"><span className="h-1.5 w-1.5 rounded-full" style={{ background: ALLOC[i][0] }} />{t(k)}</li>)}</ul>
          </div>
        </div>
      </div>
      <div className="absolute -bottom-6 -left-4 w-64 rounded-2xl border border-[#00A878]/30 bg-[#071A2B]/90 p-3.5 shadow-xl backdrop-blur-xl fade-up sm:-left-10" style={{ animationDelay: "600ms" }}>
        <div className="flex items-center gap-2 text-[10px] font-bold tracking-[0.14em] text-[#00A878]"><Sparkles className="h-3.5 w-3.5" />FINORA AI INSIGHT</div>
        <p className="mt-1.5 text-[12px] leading-relaxed text-slate-200">{t("ai_s4")}</p>
      </div>
    </div>
  );
}
