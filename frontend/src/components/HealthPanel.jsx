import { useState } from "react";
import { CheckCircle2, CircleAlert, MessageSquareWarning, RotateCcw, TriangleAlert } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import { Card, CardTitle } from "@/components/common";
import CorrectionDialog from "@/components/CorrectionDialog";

const ST = { ok: ["text-[#00A878] bg-emerald-50", CheckCircle2], review: ["text-amber-700 bg-amber-50", CircleAlert], attention: ["text-red-600 bg-red-50", TriangleAlert] };

export function HealthBadge({ level }) {
  const { t } = useApp();
  const [cls, I] = ST[level] || ST.ok;
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${cls}`}><I className="h-3 w-3" />{t(`health_${level}`)}</span>;
}

export default function HealthPanel({ health, compact, clientId, onChange }) {
  const { t, isClient } = useApp();
  const [corr, setCorr] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!health) return null;
  const checks = compact ? health.checks.filter((c) => c.level !== "ok") : health.checks;
  const mutedItems = health.muted_items || [];

  const mute = async (code, it) => {
    setBusy(true);
    try {
      await api.post("/health/mute", { client_id: it.client_id || clientId, code, item_id: it.id, label: it.label || "" });
      onChange?.();
    } finally { setBusy(false); }
  };
  const unmute = async (m) => {
    setBusy(true);
    try {
      await api.post("/health/unmute", { client_id: m.client_id || clientId, code: m.code, item_id: m.item_id });
      onChange?.();
    } finally { setBusy(false); }
  };

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
                  <span key={it.id} className="inline-flex items-center gap-1 rounded-md bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600" data-testid={`health-item-${it.id}`}>
                    {it.entity === "documents" ? t(it.label) : it.label}
                    {!isClient && it.client_id && <button onClick={() => setCorr({ ...it, code: c.code })} className="text-[#C9A227]" title={t("request_correction")} data-testid={`health-correction-${it.id}`}><MessageSquareWarning className="h-3 w-3" /></button>}
                    <button onClick={() => mute(c.code, it)} disabled={busy} className="text-[#00A878] hover:text-emerald-700 disabled:opacity-40" title={t("health_mute")} data-testid={`health-mute-${it.id}`}><CheckCircle2 className="h-3.5 w-3.5" /></button>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {!checks.length && <div className="py-4 text-center text-sm text-[#00A878]">{t("health_ok")}</div>}
      </div>

      {!compact && mutedItems.length > 0 && (
        <div className="mt-4 rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-3 py-2.5" data-testid="health-muted-section">
          <div className="mb-2 text-xs font-semibold text-slate-500">{t("health_muted_section")} · <span className="font-num">{mutedItems.length}</span></div>
          <div className="flex flex-wrap gap-1.5">
            {mutedItems.map((m) => (
              <span key={`${m.code}:${m.item_id}`} className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-0.5 text-[11px] text-slate-500 line-through" data-testid={`health-muted-${m.item_id}`}>
                <span className="text-[10px] text-slate-400">{t(`hc_${m.code}`)}:</span>{m.label || m.item_id}
                <button onClick={() => unmute(m)} disabled={busy} className="ml-0.5 text-slate-400 no-underline hover:text-[#00A878] disabled:opacity-40" title={t("health_unmute")} data-testid={`health-unmute-${m.item_id}`}><RotateCcw className="h-3 w-3" /></button>
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="mt-3 text-[11px] text-slate-500">{t("health_note")}</p>
      <CorrectionDialog open={!!corr} onOpenChange={(o) => !o && setCorr(null)} clientId={corr?.client_id || clientId}
        entity={corr?.entity === "clients" ? "cashflows" : corr?.entity} targetId={corr?.entity === "documents" ? null : corr?.id} targetLabel={corr ? `${t(`hc_${corr.code}`)}: ${corr.entity === "documents" ? t(corr.label) : corr.label}` : ""} />
    </Card>
  );
}
