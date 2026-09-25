import { useState } from "react";
import { Link } from "react-router-dom";
import { Bell } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useApp } from "@/context/AppContext";
import { api, useApi } from "@/lib/api";
import { Card, PageHeader, Empty } from "@/components/common";
import { fmtDateTime } from "@/lib/format";

function Item({ n, onRead }) {
  const { t, clientName } = useApp();
  return (
    <Link to={n.link || "/notifications"} onClick={() => onRead(n)} className={`flex items-start gap-3 border-b px-4 py-3 last:border-0 hover:bg-slate-50 ${n.read ? "" : "bg-emerald-50/40"}`} data-testid={`notification-${n.id}`}>
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read ? "bg-slate-300" : "bg-[#00A878]"}`} />
      <div className="min-w-0 flex-1">
        <div className="text-sm text-slate-800">{t(`ntf_${n.kind}`)}{n.params?.label && <span className="text-slate-500"> — {n.params.entity ? `${t(n.params.entity)}: ` : ""}{n.params.label}</span>}</div>
        <div className="text-[11px] text-slate-500">{n.actor_name || "FINORA"} · {clientName(n.client_id)} · <span className="font-num">{fmtDateTime(n.created_at)}</span></div>
      </div>
    </Link>
  );
}

function useNotifications() {
  const r = useApi("/notifications");
  const read = async (n) => { if (!n.read) { await api.post(`/notifications/${n.id}/read`).catch(() => {}); r.reload(); } };
  const readAll = async () => { await api.post("/notifications/read-all").catch(() => {}); r.reload(); };
  return { ...r, read, readAll };
}

export function NotificationBell() {
  const { t } = useApp();
  const { data, read, readAll } = useNotifications();
  const [open, setOpen] = useState(false);
  const n = data?.unread || 0;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button className="relative rounded-xl p-2 text-slate-600 hover:bg-slate-100" data-testid="header-notifications-btn">
          <Bell className="h-5 w-5" strokeWidth={1.7} />
          {n > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#00A878] px-1 text-[10px] font-bold text-white" data-testid="header-notifications-count">{n}</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-0" data-testid="header-notifications-panel">
        <div className="flex items-center border-b px-4 py-3 text-sm font-semibold text-[#071A2B]">{t("notifications")}
          <button onClick={readAll} className="ml-auto text-xs font-medium text-[#00A878]" data-testid="notifications-read-all">{t("mark_all_read")}</button></div>
        <div className="max-h-96 overflow-y-auto" onClick={() => setOpen(false)}>
          {!(data?.items || []).length && <div className="p-4 text-sm text-slate-400">{t("no_alerts")}</div>}
          {(data?.items || []).slice(0, 15).map((x) => <Item key={x.id} n={x} onRead={read} />)}
        </div>
        <Link to="/notifications" onClick={() => setOpen(false)} className="block border-t px-4 py-2 text-center text-xs font-semibold text-[#00A878]">{t("view_all")}</Link>
      </PopoverContent>
    </Popover>
  );
}

export default function Notifications() {
  const { t } = useApp();
  const { data, read, readAll } = useNotifications();
  return (
    <div data-testid="notifications-page">
      <PageHeader eyebrow="Notification Center" title={t("notifications")}>
        <button onClick={readAll} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium" data-testid="notifications-page-read-all">{t("mark_all_read")}</button>
      </PageHeader>
      <Card className="p-0 sm:p-0">{!(data?.items || []).length ? <Empty text={t("no_data")} /> : data.items.map((x) => <Item key={x.id} n={x} onRead={read} />)}</Card>
    </div>
  );
}
