import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import { api, downloadFile, errMsg, useApi } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { Card, CardTitle } from "@/components/common";

export function TwoFactorCard() {
  const { t, user, setUser } = useApp();
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const refresh = async () => setUser((await api.get("/auth/me")).data);
  const call = async (path) => {
    try { await api.post(`/auth/2fa/${path}`, { code }); toast.success(t("saved")); setSetup(null); setCode(""); refresh(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card data-testid="twofa-card">
      <CardTitle right={<span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${user.totp_enabled ? "bg-emerald-50 text-[#00A878]" : "bg-slate-100 text-slate-500"}`} data-testid="twofa-status">{t(user.totp_enabled ? "twofa_on" : "twofa_off")}</span>}>{t("two_factor")}</CardTitle>
      {!user.totp_enabled && !setup && <Button className="btn-emerald" onClick={async () => setSetup((await api.post("/auth/2fa/setup")).data)} data-testid="twofa-setup-btn">{t("enable_2fa")}</Button>}
      {setup && (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">{t("scan_qr")}</p>
          <div className="inline-block rounded-xl bg-white p-3 shadow-sm"><QRCodeSVG value={setup.uri} size={160} /></div>
          <div className="font-num text-xs text-slate-500" data-testid="twofa-secret">{setup.secret}</div>
        </div>
      )}
      {(setup || user.totp_enabled) && (
        <div className="mt-3 flex max-w-sm gap-2">
          <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder={t("enter_code")} inputMode="numeric" data-testid="twofa-code-input" />
          <Button className={user.totp_enabled ? "" : "btn-emerald"} variant={user.totp_enabled ? "outline" : "default"} onClick={() => call(user.totp_enabled ? "disable" : "enable")} data-testid="twofa-confirm-btn">{t(user.totp_enabled ? "disable_2fa" : "verify")}</Button>
        </div>
      )}
    </Card>
  );
}

export function ConsentHistory() {
  const { t, user } = useApp();
  const { data } = useApi("/consents/status");
  return (
    <Card data-testid="consent-history">
      <CardTitle>{t("consent_history")}</CardTitle>
      <div className="space-y-1.5 text-sm">
        {(data?.history || []).map((h) => <div key={h.id} className="flex gap-3"><span className="flex-1">{t(`consent_${h.doc}`)}</span><span className="font-num text-xs text-slate-500">v{h.version} · {fmtDateTime(h.agreed_at)} · {h.ip}</span></div>)}
        {!(data?.history || []).length && <div className="text-slate-400">—</div>}
      </div>
      {user.role === "admin" && <Button variant="outline" className="mt-4" onClick={() => downloadFile("/admin/backup", "finora_backup.json").catch((e) => toast.error(errMsg(e)))} data-testid="backup-download-btn">{t("download_backup")}</Button>}
    </Card>
  );
}
