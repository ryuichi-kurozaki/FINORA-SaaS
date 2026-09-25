import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import { LogoFull } from "@/components/Logo";

function Frame({ icon, title, testid }) {
  const { t, user } = useApp();
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F7F9FC] px-4">
      <div className="glass-card w-full max-w-md rounded-3xl p-8 text-center" data-testid={testid}>
        <LogoFull className="mx-auto h-12 w-auto" />
        <div className="mt-6 flex justify-center">{icon}</div>
        <h1 className="mt-4 font-display text-xl font-bold text-[#071A2B]">{title}</h1>
        <Link to={user && user.role === "admin" && user.role !== "client" ? "/billing" : "/billing"} className="btn-emerald mt-6 inline-flex rounded-xl px-5 py-2.5 text-sm font-semibold" data-testid="payment-back-btn">{t("back_to_billing")}</Link>
      </div>
    </div>
  );
}

export function PaymentSuccess() {
  const { t } = useApp();
  const [params] = useSearchParams();
  const [state, setState] = useState("pending");
  useEffect(() => {
    const sid = params.get("session_id");
    if (!sid) { setState("failed"); return; }
    let n = 0, stop = false;
    const poll = async () => {
      try {
        const { data } = await api.get(`/payments/status/${sid}`);
        if (data.payment_status === "paid") return setState("paid");
        if (["expired", "failed"].includes(data.payment_status)) return setState("failed");
      } catch { /* retry */ }
      if (!stop && ++n < 15) setTimeout(poll, 2000); else if (!stop) setState("failed");
    };
    poll();
    return () => { stop = true; };
  }, [params]);
  if (state === "paid") return <Frame testid="payment-success" icon={<CheckCircle2 className="h-14 w-14 text-[#00A878]" />} title={t("payment_success")} />;
  if (state === "failed") return <Frame testid="payment-failed" icon={<XCircle className="h-14 w-14 text-red-500" />} title={t("payment_failed")} />;
  return <Frame testid="payment-pending" icon={<Loader2 className="h-14 w-14 animate-spin text-[#00A878]" />} title={t("payment_processing")} />;
}

export function PaymentCancel() {
  const { t } = useApp();
  return <Frame testid="payment-cancel" icon={<XCircle className="h-14 w-14 text-slate-400" />} title={t("payment_cancelled")} />;
}
