import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { Card, Empty, PageHeader, Spinner } from "@/components/common";
import { useScopeLabel } from "@/lib/useDashboard";

const DOT = { CREATE: "bg-[#00A878]", UPDATE: "bg-sky-500", DELETE: "bg-red-500", UPLOAD: "bg-[#C9A227]", CONSULTANT_REQUEST: "bg-[#C9A227]", MEETING: "bg-[#071A2B]" };

export function TimelineList({ clientId }) {
  const { t } = useApp();
  const { data, loading } = useApi(clientId ? `/timeline?client_id=${clientId}` : null, [clientId]);
  if (!clientId) return <Empty text={t("select_client_first")} />;
  if (loading) return <Spinner />;
  if (!data?.length) return <Empty text={t("no_data")} />;
  return (
    <ol className="relative ml-2 border-l border-slate-200" data-testid="timeline-list">
      {data.map((e, i) => (
        <li key={i} className="mb-4 ml-5" data-testid={`timeline-item-${i}`}>
          <span className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-white ${DOT[(e.action || "").toUpperCase()] || "bg-slate-400"}`} />
          <div className="text-[11px] text-slate-400 font-num">{fmtDateTime(e.at)}</div>
          <div className="text-sm text-slate-800"><b className="text-[#071A2B]">{t(`tl_${(e.action || "").toUpperCase()}`)}</b> · {t(e.entity)}{e.label && <span className="text-slate-600"> — {t(e.label)}</span>}</div>
          {e.user_name && <div className="text-[11px] text-slate-500">{e.user_name} ({t(e.user_role === "client" ? "client_role" : e.user_role)})</div>}
        </li>
      ))}
    </ol>
  );
}

export default function Timeline() {
  const { t, scopeClient } = useApp();
  const scope = useScopeLabel();
  return (
    <div data-testid="timeline-page">
      <PageHeader eyebrow={`Timeline · ${scope}`} title={t("timeline")} />
      <Card><TimelineList clientId={scopeClient} /></Card>
    </div>
  );
}
