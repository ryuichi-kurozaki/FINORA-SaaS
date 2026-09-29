import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/common";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";

export default function LineLink() {
  const { t } = useApp();
  const [st, setSt] = useState(null);
  const [code, setCode] = useState("");

  const load = async () => {
    try { setSt((await api.get("/line/status")).data); } catch { setSt({ configured: false, linked: false }); }
  };
  useEffect(() => { load(); }, []);

  const issue = async () => {
    try { setCode((await api.post("/line/link-code")).data.code); } catch (e) { toast.error(errMsg(e)); }
  };
  const unlink = async () => {
    try { await api.delete("/line/link"); setCode(""); await load(); toast.success(t("saved")); } catch (e) { toast.error(errMsg(e)); }
  };

  if (!st) return null;
  return (
    <Card data-testid="line-link">
      <CardTitle><span className="inline-flex items-center gap-2"><MessageCircle className="h-4 w-4 text-emerald-600" />{t("line_link")}</span></CardTitle>
      {!st.configured ? (
        <p className="text-xs text-slate-500" data-testid="line-not-configured">{t("line_not_configured")}</p>
      ) : (
        <>
          <p className="mb-4 text-xs leading-relaxed text-slate-500">{t("line_link_note")}</p>
          <div className="mb-4 flex items-center gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${st.linked ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`} data-testid="line-link-status">
              {st.linked ? t("line_linked") : t("line_not_linked")}
            </span>
            {st.bot_id && (
              <a href={`https://line.me/R/ti/p/${encodeURIComponent(st.bot_id)}`} target="_blank" rel="noreferrer"
                className="text-xs font-semibold text-emerald-700 underline" data-testid="line-add-friend">{t("line_add_friend")}</a>
            )}
          </div>
          {st.linked ? (
            <Button variant="outline" onClick={unlink} data-testid="line-unlink-btn">{t("line_unlink")}</Button>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Button className="btn-emerald" onClick={issue} data-testid="line-issue-code-btn">{t("line_issue_code")}</Button>
              {code && (
                <div>
                  <div className="font-mono text-2xl tracking-[0.3em] text-slate-900" data-testid="line-link-code">{code}</div>
                  <div className="text-xs text-slate-500">{t("line_code_hint")}</div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </Card>
  );
}
