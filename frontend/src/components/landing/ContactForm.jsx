import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";

const EMPTY = { name: "", company: "", email: "", phone: "", inquiry_type: "corporate", message: "", website: "" };

export default function ContactForm() {
  const { t, lang } = useApp();
  const [f, setF] = useState(EMPTY);
  const [state, setState] = useState({ busy: false, ok: false, err: "" });
  const on = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true, ok: false, err: "" });
    try {
      await api.post("/public/inquiries", { ...f, lang });
      setF(EMPTY);
      setState({ busy: false, ok: true, err: "" });
    } catch (e2) { setState({ busy: false, ok: false, err: errMsg(e2) }); }
  };

  if (state.ok) return (
    <div className="flex flex-col items-center rounded-3xl border border-emerald-200 bg-emerald-50/60 p-10 text-center" data-testid="contact-success">
      <CheckCircle2 className="h-10 w-10 text-[#00A878]" />
      <p className="mt-4 font-medium text-[#071A2B]">{t("sent_ok")}</p>
      <Button variant="outline" className="mt-6" onClick={() => setState({ busy: false, ok: false, err: "" })} data-testid="contact-send-another">{t("send")}</Button>
    </div>
  );

  const lbl = "mb-1.5 block text-xs font-medium text-slate-600";
  return (
    <form onSubmit={submit} className="glass-card grid gap-4 rounded-3xl p-6 sm:grid-cols-2 sm:p-8" data-testid="contact-form">
      <label><span className={lbl}>{t("name")} *</span><Input required value={f.name} onChange={on("name")} className="h-11" data-testid="contact-name" /></label>
      <label><span className={lbl}>{t("company")}</span><Input value={f.company} onChange={on("company")} className="h-11" data-testid="contact-company" /></label>
      <label><span className={lbl}>{t("email")} *</span><Input required type="email" value={f.email} onChange={on("email")} className="h-11" data-testid="contact-email" /></label>
      <label><span className={lbl}>{t("phone_opt")}</span><Input value={f.phone} onChange={on("phone")} className="h-11" data-testid="contact-phone" /></label>
      <label className="sm:col-span-2"><span className={lbl}>{t("inquiry_type")}</span>
        <select value={f.inquiry_type} onChange={on("inquiry_type")} className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" data-testid="contact-type">
          {["individual", "corporate", "consulting_firm", "other"].map((k) => <option key={k} value={k}>{t(k)}</option>)}
        </select>
      </label>
      <label className="sm:col-span-2"><span className={lbl}>{t("message")} *</span>
        <textarea required minLength={5} rows={5} value={f.message} onChange={on("message")} className="w-full rounded-lg border border-slate-200 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40" data-testid="contact-message" />
      </label>
      <input tabIndex={-1} autoComplete="off" value={f.website} onChange={on("website")} className="hidden" aria-hidden="true" />
      {state.err && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 sm:col-span-2" data-testid="contact-error">{state.err}</div>}
      <div className="flex flex-col gap-3 sm:col-span-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[11px] text-slate-500">{t("agree")} <Link to="/legal" className="text-[#00A878] underline-offset-2 hover:underline">{t("privacy")}</Link></p>
        <Button type="submit" disabled={state.busy} className="btn-emerald h-11 rounded-full px-8" data-testid="contact-submit"><Send className="mr-2 h-4 w-4" />{state.busy ? t("loading") : t("send")}</Button>
      </div>
    </form>
  );
}
