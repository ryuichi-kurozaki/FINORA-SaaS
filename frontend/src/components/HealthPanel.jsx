import { useState } from "react";
import { CheckCircle2, CircleAlert, MessageSquareWarning, TriangleAlert } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { Card, CardTitle } from "@/components/common";
import CorrectionDialog from "@/components/CorrectionDialog";

const ST = { ok: ["text-[#00A878] bg-emerald-50", CheckCircle2], review: ["text-amber-700 bg-amber-50", CircleAlert], attention: ["text-red-600 bg-red-50", TriangleAlert] };

export function HealthBadge({ level }) {
  const { t } = useApp();
  const [cls, I] = ST[level] || ST.ok;
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${cls}`}><I className="h-3 w-3" />{t(`health_${level}`)}</span>;
}

export default function HealthPanel({ health, compact, clientId }) {
  const { t, isClient } = useApp();
  const [corr, setCorr] = useState(null);
  if (!health) return null;
  const checks = compact ? health.checks.filter((c) => c.level !== "ok") : health.checks;
  return (
    <Card data-testid="data-health-panel">
      <CardTitle right={<HealthBadge level={health.status} />}>{t("data_health")} · <span className="font-num">{health.score}</span>/100</CardTitle>
      <div className="space-y-2">
        {checks.map((c) => (
          <div key={c.code} className="rounded-xl border border-slate-100 bg-white px-3 py-2.5" data-testid={`health-check-${c.code}`}>
            <div className="flex items-center gap-2 text-sm">
              <span className="flex-1 text-slate-800">{t(`hc_${c.code}`)}</span>
              {c.count > 0 && <span className="font-num text-xs text-slate-500">{c.count}</span>}
              <HealthBadge level={c.level} />
            </div>
            {!compact && c.items.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {c.items.slice(0, 12).map((it) => (
                  <span key={it.id} className="inline-flex items-center gap-1 rounded-md bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600">
                    {it.entity === "documents" ? t(it.label) : it.label}
                    {!isClient && it.client_id && <button onClick={() => setCorr({ ...it, code: c.code })} className="text-[#C9A227]" title={t("request_correction")} data-testid={`health-correction-${it.id}`}><MessageSquareWarning className="h-3 w-3" /></button>}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {!checks.length && <div className="py-4 text-center text-sm text-[#00A878]">{t("health_ok")}</div>}
      </div>
      <p className="mt-3 text-[11px] text-slate-500">{t("health_note")}</p>
      <CorrectionDialog open={!!corr} onOpenChange={(o) => !o && setCorr(null)} clientId={corr?.client_id || clientId}
        entity={corr?.entity === "clients" ? "cashflows" : corr?.entity} targetId={corr?.entity === "documents" ? null : corr?.id} targetLabel={corr ? `${t(`hc_${corr.code}`)}: ${corr.entity === "documents" ? t(corr.label) : corr.label}` : ""} />
    </Card>
  );
}
