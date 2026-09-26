import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

export default function WaHealthBanner() {
  const { t, user } = useApp();
  const { data, reload } = useApi("/system/wa-health");
  useEffect(() => { const id = setInterval(reload, 300000); return () => clearInterval(id); }, [reload]);
  if (!data?.configured || data.ok) return null;
  return (
    <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" data-testid="wa-health-banner">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div><div className="font-semibold">{t("wa_down_title")}</div>
        <div className="text-xs">{t("wa_down_desc")}{data.since && ` (${fmtDateTime(data.since)}〜)`}{user.platform_admin && data.detail && ` — ${data.detail}`}</div></div>
    </div>
  );
}
