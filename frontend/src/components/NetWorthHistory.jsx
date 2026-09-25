import { useMemo, useState } from "react";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { Card, CardTitle, Spinner } from "@/components/common";
import { TrendChart } from "@/components/charts";

const RANGES = [["1M", 30], ["3M", 91], ["6M", 182], ["1Y", 365], ["3Y", 1095], ["5Y", 1826], ["ALL", 99999]];

export default function NetWorthHistory({ clientId, className = "" }) {
  const { t } = useApp();
  const { data } = useApi(`/history${clientId ? `?client_id=${clientId}` : ""}`, [clientId]);
  const [r, setR] = useState("1Y");
  const rows = useMemo(() => {
    const days = RANGES.find((x) => x[0] === r)[1];
    const from = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
    return (data || []).filter((x) => x.date >= from);
  }, [data, r]);
  return (
    <Card className={className} data-testid="networth-history">
      <CardTitle right={
        <div className="flex flex-wrap gap-1">{RANGES.map(([k]) => (
          <button key={k} onClick={() => setR(k)} data-testid={`history-range-${k}`}
            className={`rounded-md px-2 py-0.5 font-num text-[11px] font-semibold ${r === k ? "bg-[#071A2B] text-white" : "text-slate-500 hover:bg-slate-100"}`}>{k}</button>
        ))}</div>
      }>{t("net_worth_history")}</CardTitle>
      {!data ? <Spinner /> : <TrendChart data={rows} keys={["net_worth", "total_assets", "total_liabilities"]} testid="chart-networth-history" />}
      <p className="mt-2 text-[10px] text-slate-400">{t("net_worth")} = {t("total_assets")} − {t("total_liabilities")}</p>
    </Card>
  );
}
