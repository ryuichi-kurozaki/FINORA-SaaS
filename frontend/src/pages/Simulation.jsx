import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import { useScopeLabel } from "@/lib/useDashboard";
import { compact, yen } from "@/lib/format";
import { Card, CardTitle, PageHeader, Spinner } from "@/components/common";
import { ProjectionChart } from "@/components/charts";

const DEF = { years: 20, bull_return: 8, base_return: 5, bear_return: 1, equity_shock: 0, fx_shock: 0, rate_change: 0, real_estate_shock: 0, income_change: 0, expense_change: 0, reinvest: true };
const COMPOUND = [["years", 1, 40, 1], ["bull_return", 0, 15, 0.5], ["base_return", -2, 10, 0.5], ["bear_return", -10, 5, 0.5]];
const STRESS = [["equity_shock", -50, 50, 5], ["fx_shock", -30, 30, 5], ["rate_change", -1, 5, 0.25], ["real_estate_shock", -40, 40, 5], ["income_change", -50, 50, 5], ["expense_change", -30, 50, 5]];

function Param({ k, min, max, step, p, set }) {
  const { t } = useApp();
  return (
    <div>
      <div className="mb-2 flex justify-between text-xs"><span className="text-slate-600">{t(k)}</span><span className="font-num font-semibold text-[#071A2B]">{p[k]}</span></div>
      <Slider min={min} max={max} step={step} value={[p[k]]} onValueChange={([v]) => set({ ...p, [k]: v })} data-testid={`sim-${k}`} />
    </div>
  );
}

export default function Simulation() {
  const { t, lang, scopeClient } = useApp();
  const scope = useScopeLabel();
  const [p, setP] = useState(DEF);
  const [contrib, setContrib] = useState("");
  const [res, setRes] = useState(null);
  useEffect(() => {
    const h = setTimeout(() => {
      api.post("/simulation", { client_id: scopeClient || null, params: { ...p, monthly_contribution: contrib === "" ? null : contrib } }).then((r) => setRes(r.data));
    }, 250);
    return () => clearTimeout(h);
  }, [p, contrib, scopeClient]);
  return (
    <div data-testid="simulation-page">
      <PageHeader eyebrow={`Simulation · ${scope}`} title={t("simulation")} sub={t("scenario_compare")}>
        <Button variant="outline" size="sm" onClick={() => { setP(DEF); setContrib(""); }} data-testid="sim-reset"><RotateCcw className="mr-1 h-4 w-4" />{t("reset")}</Button>
      </PageHeader>
      <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <div className="space-y-6">
          <Card>
            <CardTitle>{t("compound")}</CardTitle>
            <div className="space-y-5">
              <label className="block">
                <span className="mb-1.5 block text-xs text-slate-600">{t("monthly_contribution")} (¥)</span>
                <input type="number" value={contrib} placeholder={res ? String(res.contribution_m) : ""} onChange={(e) => setContrib(e.target.value)} className="h-10 w-full rounded-lg border border-slate-200 px-3 font-num text-sm" data-testid="sim-monthly-contribution" />
              </label>
              {COMPOUND.map(([k, a, b, s]) => <Param key={k} k={k} min={a} max={b} step={s} p={p} set={setP} />)}
              <div className="flex items-center justify-between"><span className="text-xs text-slate-600">{t("reinvest")}</span><Switch checked={p.reinvest} onCheckedChange={(v) => setP({ ...p, reinvest: v })} data-testid="sim-reinvest" /></div>
            </div>
          </Card>
          <Card><CardTitle>{t("stress_params")}</CardTitle><div className="space-y-5">{STRESS.map(([k, a, b, s]) => <Param key={k} k={k} min={a} max={b} step={s} p={p} set={setP} />)}</div></Card>
        </div>
        <div className="space-y-6">
          {!res ? <Spinner /> : (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                {Object.entries(res.milestones).map(([y, r]) => (
                  <div key={y} className="glass-card rounded-2xl p-5" data-testid={`sim-milestone-${y}`}>
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">{y} {t("after_years")}</div>
                    {["bull", "base", "bear"].map((k) => (
                      <div key={k} className="mt-2 flex items-baseline justify-between">
                        <span className={`text-xs ${k === "bull" ? "text-[#00A878]" : k === "bear" ? "text-[#C9A227]" : "text-[#071A2B]"}`}>{t(k)}</span>
                        <span className={`font-num ${k === "base" ? "text-lg font-semibold text-[#071A2B]" : "text-sm text-slate-600"}`}>{compact(r[k], lang)}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
              <Card>
                <CardTitle right={<span className="text-[10px] font-semibold uppercase tracking-wider text-amber-600">{t("estimate")}</span>}>{t("scenario_compare")} — {t("net_worth")}</CardTitle>
                <ProjectionChart rows={res.rows} height={360} testid="sim-chart" />
                <div className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
                  <div>{t("net_worth")} (0): <span className="font-num text-slate-800">{yen(res.start_net_worth)}</span></div>
                  <div>{t("monthly_contribution")}: <span className="font-num text-slate-800">{yen(res.contribution_m)}</span></div>
                  <div>{t("dividend_yield_param")}: <span className="font-num text-slate-800">{res.assumptions.dividend_yield.toFixed(2)}%</span></div>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
