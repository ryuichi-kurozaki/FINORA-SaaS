import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Bell, Brain, Briefcase, CalendarClock, ChartLine, ChartPie, FileBarChart, FolderLock, Gauge, Landmark, LayoutDashboard, LogOut, Menu, Settings, ShieldAlert, Telescope, Users, Wallet, Scale, Waves } from "lucide-react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useApp } from "@/context/AppContext";
import { useApi } from "@/lib/api";
import { LANGS } from "@/i18n/dict";
import { Logo } from "@/components/Logo";

export const NAV = [
  ["dashboard", "Dashboard", "/", LayoutDashboard], ["clients", "Clients", "/clients", Users], ["assets", "Assets", "/assets", Wallet],
  ["portfolio", "Portfolio", "/portfolio", ChartPie], ["accounts", "Accounts", "/accounts", Landmark], ["liabilities", "Liabilities", "/liabilities", Scale],
  ["cashflow", "Cash Flow", "/cashflow", Waves], ["analytics", "Analytics", "/analytics", ChartLine], ["simulation", "Simulation", "/simulation", Telescope],
  ["risk", "Risk", "/risk", ShieldAlert], ["ai_insight", "AI Insight", "/ai", Brain], ["consulting", "Consulting", "/consulting", Briefcase],
  ["reports", "Reports", "/reports", FileBarChart], ["documents", "Documents", "/documents", FolderLock], ["tasks", "Tasks", "/tasks", CalendarClock],
  ["settings", "Settings", "/settings", Settings],
];

function SideNav({ onNavigate }) {
  const { t, lang, user } = useApp();
  const items = user.role === "client" ? NAV.filter(([k]) => k !== "clients") : NAV;
  return (
    <div className="flex h-full flex-col">
      <div className="px-6 pb-6 pt-7"><Logo light tagline /></div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4 sidebar-scroll">
        {items.map(([k, label, to, Icon]) => (
          <NavLink key={k} to={to} end={to === "/"} onClick={onNavigate} data-testid={`sidebar-nav-${k}`}
            className={({ isActive }) => `nav-item group ${isActive ? "nav-active" : ""}`}>
            <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.7} />
            <span className="flex-1">
              <span className="block text-[13px] font-medium">{label}</span>
              {lang !== "en" && <span className="block text-[10px] text-slate-500 group-[.nav-active]:text-emerald-200/70">{t(k)}</span>}
            </span>
            {k === "ai_insight" && <span className="rounded bg-[#C9A227]/15 px-1.5 py-0.5 text-[9px] font-bold tracking-wider text-[#C9A227]">AI</span>}
          </NavLink>
        ))}
      </nav>
      <div className="mx-4 mb-5 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-[11px] text-slate-400">
        <div className="flex items-center gap-2 text-slate-300"><Gauge className="h-3.5 w-3.5 text-[#00A878]" />{user.tenant?.name}</div>
        <div className="mt-1 text-[#C9A227]">Premium Plan</div>
      </div>
    </div>
  );
}

function Alerts() {
  const { t } = useApp();
  const { data } = useApi("/tasks/alerts");
  const n = (data || []).length;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="relative rounded-xl p-2 text-slate-600 transition-colors hover:bg-slate-100" data-testid="header-alerts-btn">
          <Bell className="h-5 w-5" strokeWidth={1.7} />
          {n > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white" data-testid="header-alerts-count">{n}</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0" data-testid="header-alerts-panel">
        <div className="border-b px-4 py-3 text-sm font-semibold text-[#071A2B]">{t("alerts")}</div>
        <div className="max-h-80 overflow-y-auto">
          {!n && <div className="p-4 text-sm text-slate-400">{t("no_alerts")}</div>}
          {(data || []).map((a) => (
            <div key={a.id} className="flex items-start gap-3 border-b px-4 py-3 last:border-0">
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${a.overdue ? "bg-red-500" : "bg-[#C9A227]"}`} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm text-slate-800">{a.title}</div>
                <div className="text-xs text-slate-500">{a.client_name || t(a.kind)} · <span className="font-num">{a.due_date}</span> · {a.overdue ? t("overdue") : t("due_soon")}</div>
              </div>
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function Header({ onMenu }) {
  const { t, lang, setLang, user, logout, clients, scopeClient, setScopeClient } = useApp();
  const nav = useNavigate();
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200/70 bg-[#F7F9FC]/80 px-4 backdrop-blur-xl sm:px-8">
      <button className="rounded-lg p-2 lg:hidden" onClick={onMenu} data-testid="mobile-menu-btn"><Menu className="h-5 w-5" /></button>
      {user.role !== "client" ? (
        <select value={scopeClient} onChange={(e) => setScopeClient(e.target.value)} data-testid="header-client-scope"
          className="h-9 w-[130px] min-w-0 rounded-xl sm:w-auto sm:max-w-[220px] border border-slate-200 bg-white px-3 text-sm text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40">
          <option value="">{t("all_clients")} ({clients.length})</option>
          {clients.map((c) => <option key={c.id} value={c.id}>{c.corporate_name || c.name}</option>)}
        </select>
      ) : <span className="text-sm font-medium text-slate-700">{user.name}</span>}
      <div className="ml-auto flex items-center gap-1 sm:gap-2">
        <div className="hidden items-center rounded-xl border border-slate-200 bg-white p-0.5 sm:flex">
          {LANGS.map((l) => (
            <button key={l.code} onClick={() => setLang(l.code)} data-testid={`language-selector-${l.code}`}
              className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${lang === l.code ? "bg-[#071A2B] text-white" : "text-slate-500 hover:text-[#071A2B]"}`}>{l.short}</button>
          ))}
        </div>
        <select className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-xs sm:hidden" value={lang} onChange={(e) => setLang(e.target.value)} data-testid="language-selector-mobile">
          {LANGS.map((l) => <option key={l.code} value={l.code}>{l.short}</option>)}
        </select>
        <Alerts />
        <div className="hidden text-right md:block">
          <div className="text-sm font-semibold text-[#071A2B]" data-testid="header-user-name">{user.name}</div>
          <div className="text-[11px] text-slate-500">{t(user.role === "client" ? "client_role" : user.role)}</div>
        </div>
        <button onClick={async () => { await logout(); nav("/login"); }} className="rounded-xl p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-red-600" data-testid="logout-btn" title={t("logout")}>
          <LogOut className="h-5 w-5" strokeWidth={1.7} />
        </button>
      </div>
    </header>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-[#F7F9FC]">
      <aside className="sidebar fixed inset-y-0 left-0 z-40 hidden w-[260px] lg:block" data-testid="sidebar"><SideNav /></aside>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="sidebar w-[270px] border-0 p-0"><SideNav onNavigate={() => setOpen(false)} /></SheetContent>
      </Sheet>
      <div className="lg:pl-[260px]">
        <Header onMenu={() => setOpen(true)} />
        <main className="mx-auto max-w-[1500px] px-4 py-8 sm:px-8"><Outlet /></main>
      </div>
    </div>
  );
}
