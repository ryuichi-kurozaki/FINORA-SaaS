import ClientOverviewTable from "@/components/ClientOverviewTable";
import { Link } from "react-router-dom";
import { Building2, ChevronRight, UserRound } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { PageHeader } from "@/components/common";
import EntityManager from "@/components/EntityManager";
import HandoverDialog from "@/components/HandoverDialog";

export default function Clients() {
  const { t, clients, user } = useApp();
  return (
    <div data-testid="clients-page">
      <PageHeader eyebrow="CRM" title={t("clients")} sub={t("derived_note")}>{user.role === "admin" && !user.demo && <HandoverDialog />}</PageHeader>
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {clients.map((c, i) => (
          <Link key={c.id} to={`/clients/${c.id}`} data-testid={`client-card-${c.id}`} style={{ animationDelay: `${i * 60}ms` }}
            className="glass-card group fade-up rounded-2xl p-5 hover:-translate-y-0.5 hover:border-[#00A878]/40">
            <div className="flex items-start gap-3">
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${c.client_type === "corporate" ? "bg-[#071A2B] text-[#C9A227]" : "bg-emerald-50 text-[#00A878]"}`}>
                {c.client_type === "corporate" ? <Building2 className="h-5 w-5" /> : <UserRound className="h-5 w-5" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold text-[#071A2B]">{c.corporate_name || c.name}</div>
                <div className="truncate text-xs text-slate-500">{c.corporate_name ? c.name : c.occupation || c.email}</div>
              </div>
              <ChevronRight className="h-4 w-4 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-[#00A878]" />
            </div>
            <div className="mt-4 flex flex-wrap gap-1.5 text-[11px]">
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">{t(c.client_type)}</span>
              {c.status && <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-emerald-700">{t(c.status)}</span>}
              {c.risk_tolerance && <span className="rounded-md bg-amber-50 px-2 py-0.5 text-amber-700">{t("risk_tolerance")}: {t(c.risk_tolerance)}</span>}
            </div>
          </Link>
        ))}
      </div>
      <ClientOverviewTable />
      <EntityManager entity="clients" clientId="" title={t("clients")} />
    </div>
  );
}
