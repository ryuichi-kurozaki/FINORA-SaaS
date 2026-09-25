import { Link } from "react-router-dom";
import { CalendarClock, FileWarning, MessageSquareWarning, MessagesSquare, PencilLine } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { Card } from "@/components/common";

function Box({ icon: I, title, to, items, testid }) {
  const { t } = useApp();
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4" data-testid={testid}>
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-[#071A2B]"><I className="h-4 w-4 text-[#00A878]" />{title}
        <span className="ml-auto rounded-full bg-slate-100 px-2 font-num text-[11px] text-slate-600">{items.length}</span></div>
      <ul className="space-y-1 text-[12px] text-slate-600">{items.slice(0, 3).map((x, i) => <li key={i} className="truncate">• {x}</li>)}</ul>
      {to && <Link to={to} className="mt-2 inline-block text-[11px] font-semibold text-[#00A878]">{t("view_all")} →</Link>}
    </div>
  );
}

export default function ActionCenter({ health }) {
  const { t } = useApp();
  const { data: corr } = useApi("/corrections?status=open");
  const { data: reqs } = useApi("/requests");
  const { data: tasks } = useApi("/tasks/alerts");
  const bad = (health?.checks || []).filter((c) => c.level !== "ok");
  const docs = bad.find((c) => c.code === "docs_missing")?.items || [];
  return (
    <Card data-testid="client-action-center">
      <div className="mb-4 font-display text-[15px] font-bold text-[#071A2B]">{t("action_center")}</div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Box icon={PencilLine} title={t("updates_needed")} to="/data-health" testid="ac-updates" items={bad.filter((c) => c.code !== "docs_missing").map((c) => `${t(`hc_${c.code}`)} (${c.count})`)} />
        <Box icon={MessageSquareWarning} title={t("pending_corrections")} to="/consulting" testid="ac-corrections" items={(corr || []).map((c) => `${c.target_label || t(c.target_entity)}: ${c.requested_change}`)} />
        <Box icon={FileWarning} title={t("docs_needed")} to="/documents" testid="ac-docs" items={docs.map((d) => t(d.label))} />
        <Box icon={MessagesSquare} title={t("request_status")} to="/consulting" testid="ac-requests" items={(reqs || []).map((r) => `${r.title} — ${t(r.status === "new" ? "new_status" : r.status)}`)} />
        <Box icon={CalendarClock} title={t("schedule")} to="/tasks" testid="ac-schedule" items={(tasks || []).map((x) => `${x.due_date} ${x.title}`)} />
      </div>
    </Card>
  );
}
