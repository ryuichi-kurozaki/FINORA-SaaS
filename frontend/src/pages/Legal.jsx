import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { LogoFull } from "@/components/Logo";
import { LangSwitch } from "@/components/landing/Chrome";

function Block({ id, title, keys }) {
  const { t } = useApp();
  return (
    <section id={id} className="glass-card scroll-mt-8 rounded-2xl p-8">
      <h2 className="font-display text-2xl font-extrabold text-[#071A2B]">{title}</h2>
      <ol className="mt-5 list-decimal space-y-3 pl-5 text-sm leading-relaxed text-slate-600">{keys.map((k) => <li key={k}>{t(k)}</li>)}</ol>
    </section>
  );
}

export default function Legal() {
  const { t } = useApp();
  return (
    <div className="min-h-screen bg-[#F7F9FC] px-5 py-10 sm:px-8" data-testid="legal-page">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-center justify-between">
          <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-[#00A878]" data-testid="legal-back-link"><ArrowLeft className="h-4 w-4" />{t("back_home")}</Link>
          <LangSwitch />
        </div>
        <LogoFull className="h-16 w-auto" />
        <Block id="terms" title={t("terms")} keys={["legal_t1", "legal_t2", "legal_t3"]} />
        <Block id="privacy" title={t("privacy")} keys={["legal_p1", "legal_p2", "legal_p3"]} />
        <p className="text-center text-xs text-slate-400">© FINORA · www.finora.co.jp</p>
      </div>
    </div>
  );
}
