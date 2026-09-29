import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardTitle } from "@/components/common";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";
import LineLink from "@/components/LineLink";

export default function NotifyPrefs() {
  const { t, user } = useApp();
  const [phone, setPhone] = useState(user.whatsapp_phone ? `+${user.whatsapp_phone}` : "");
  const [optIn, setOptIn] = useState(!!user.whatsapp_opt_in);
  const [line, setLine] = useState(user.line_id || "");
  const save = async () => {
    try { await api.put("/auth/preferences", { whatsapp_phone: phone, whatsapp_opt_in: optIn, ...(user.role !== "client" ? { line_id: line } : {}) }); toast.success(t("saved")); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-6">
    <Card data-testid="notify-prefs"><CardTitle>{t("notify_prefs")}</CardTitle>
      <p className="mb-4 text-xs text-slate-500">{t("notify_prefs_note")}</p>
      <label className="block max-w-sm text-xs text-slate-500">{t("whatsapp_phone")}
        <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+81 90 1234 5678" className="mt-1" data-testid="whatsapp-phone-input" /></label>
      <label className="mt-3 flex items-start gap-2 text-sm"><input type="checkbox" checked={optIn} onChange={(e) => setOptIn(e.target.checked)} className="mt-1" data-testid="whatsapp-optin-check" />{t("whatsapp_opt_in")}</label>
      {user.role !== "client" && <label className="mt-3 block max-w-sm text-xs text-slate-500">{t("line_id")}
        <Input value={line} onChange={(e) => setLine(e.target.value)} placeholder="@finora123" className="mt-1" data-testid="line-id-input" /></label>}
      <Button className="btn-emerald mt-4" onClick={save} data-testid="notify-prefs-save">{t("save")}</Button>
    </Card>
    <LineLink />
    </div>
  );
}
