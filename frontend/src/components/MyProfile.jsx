import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";
import { Card, CardTitle } from "@/components/common";

const FIELDS = [
  { k: "name", req: true },
  { k: "corporate_name" },
  { k: "email" },
  { k: "phone" },
  { k: "whatsapp", label: "client_whatsapp" },
  { k: "address", wide: true },
  { k: "occupation", prefix: "occ_", opts: ["employee", "executive", "public_servant", "self_employed", "professional", "pensioner", "homemaker", "student", "unemployed", "other"] },
  { k: "business", prefix: "biz_", opts: ["manufacturing", "construction_realestate", "wholesale_retail", "finance_insurance", "it", "medical_welfare", "food_hospitality", "services", "logistics", "agriculture", "other"] },
  { k: "family", prefix: "fam_", opts: ["single", "married_no_kids", "married_kids", "single_parent", "other"] },
];

const selCls = "h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40";

export default function MyProfile() {
  const { t, refreshClients } = useApp();
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.get("/me/profile").then((r) => setForm(r.data)).catch((e) => toast.error(errMsg(e))); }, []);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const save = async () => {
    setSaving(true);
    try {
      const payload = Object.fromEntries(FIELDS.map((f) => [f.k, form[f.k] ?? ""]));
      const r = await api.put("/me/profile", payload);
      setForm(r.data);
      refreshClients && refreshClients();
      toast.success(t("saved"));
    } catch (e) { toast.error(errMsg(e)); }
    setSaving(false);
  };

  if (!form) return null;
  return (
    <Card className="max-w-3xl">
      <CardTitle>{t("my_profile")}</CardTitle>
      <p className="mb-5 text-xs text-slate-500" data-testid="my-profile-hint">{t("my_profile_hint")}</p>
      <div className="grid gap-4 sm:grid-cols-2" data-testid="my-profile-form">
        {FIELDS.map((f) => (
          <label key={f.k} className={`block ${f.wide ? "sm:col-span-2" : ""}`}>
            <span className="mb-1.5 block text-xs font-medium text-slate-600">{t(f.label || f.k)}{f.req && <span className="text-red-500"> *</span>}</span>
            {f.opts ? (
              <select className={selCls} value={form[f.k] || ""} onChange={(e) => set(f.k, e.target.value)} data-testid={`my-profile-${f.k}`}>
                <option value="">—</option>
                {form[f.k] && !f.opts.includes(String(form[f.k])) && <option value={form[f.k]}>{form[f.k]}</option>}
                {f.opts.map((o) => <option key={o} value={o}>{t(f.prefix + o)}</option>)}
              </select>
            ) : (
              <Input className="h-10" value={form[f.k] || ""} onChange={(e) => set(f.k, e.target.value)} data-testid={`my-profile-${f.k}`} />
            )}
          </label>
        ))}
      </div>
      <Button className="btn-emerald mt-6" onClick={save} disabled={saving} data-testid="my-profile-save-btn">{t("save")}</Button>
    </Card>
  );
}
