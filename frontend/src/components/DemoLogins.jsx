import { Briefcase, UserRound } from "lucide-react";
import { useApp } from "@/context/AppContext";

const PW = process.env.REACT_APP_DEMO_PASSWORD;
const ACCOUNTS = [
  ["consultant", process.env.REACT_APP_DEMO_CONSULTANT_EMAIL, Briefcase],
  ["client_role", process.env.REACT_APP_DEMO_CLIENT_EMAIL, UserRound],
].filter(([, email]) => email);

export default function DemoLogins({ onPick, active }) {
  const { t } = useApp();
  if (!PW || !ACCOUNTS.length) return null;
  return (
    <div className="mt-6 border-t border-slate-200 pt-5" data-testid="demo-logins">
      <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{t("demo_accounts")}</div>
      <div className="grid grid-cols-2 gap-2">
        {ACCOUNTS.map(([role, email, Icon]) => (
          <button key={role} type="button" onClick={() => onPick(email, PW)} data-testid={`demo-login-${role}`} title={email}
            className={`flex flex-col items-center gap-1 rounded-xl border px-2 py-2.5 text-[11px] font-medium transition-colors ${active === email ? "border-[#00A878] bg-emerald-50 text-[#00A878]" : "border-slate-200 bg-white text-slate-600 hover:border-[#00A878]/60 hover:text-[#071A2B]"}`}>
            <Icon className="h-4 w-4" strokeWidth={1.8} />{t(role)}
          </button>
        ))}
      </div>
    </div>
  );
}
