import { useState } from "react";
import { SendHorizontal } from "lucide-react";
import { toast } from "sonner";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

export default function CommentThread({ clientId, targetType, targetId, targetLabel }) {
  const { t } = useApp();
  const q = `client_id=${clientId}&target_type=${targetType}${targetId ? `&target_id=${targetId}` : ""}`;
  const { data, reload } = useApi(clientId ? `/comments?${q}` : null, [q]);
  const [body, setBody] = useState("");
  const send = async (e) => {
    e.preventDefault();
    if (!body.trim()) return;
    try {
      await api.post("/comments", { client_id: clientId, target_type: targetType, target_id: targetId, target_label: targetLabel, body });
      setBody(""); reload();
    } catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <div data-testid="comment-thread">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("comments")}</div>
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {(data || []).map((c) => (
          <div key={c.id} className={`rounded-xl px-3 py-2 text-sm ${c.author_role === "client" ? "bg-emerald-50" : "bg-slate-100"}`} data-testid={`comment-${c.id}`}>
            <div className="mb-0.5 text-[11px] text-slate-500">{c.author_name} · {t(c.author_role === "client" ? "client_role" : c.author_role)} · <span className="font-num">{fmtDateTime(c.created_at)}</span></div>
            <div className="whitespace-pre-wrap text-slate-800">{c.body}</div>
          </div>
        ))}
      </div>
      <form onSubmit={send} className="mt-2 flex gap-2">
        <input value={body} onChange={(e) => setBody(e.target.value)} placeholder={t("add_comment")} className="h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#00A878]/40" data-testid="comment-input" />
        <button className="btn-emerald rounded-lg px-3" data-testid="comment-send"><SendHorizontal className="h-4 w-4" /></button>
      </form>
    </div>
  );
}
