import { useEffect, useRef, useState } from "react";
import { SendHorizontal, Sparkles, User } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";
import { AIBadge, AIThinking } from "@/components/common";

const PROMPTS = ["p_overview", "p_change", "p_risk", "p_cashflow", "p_projection", "p_report"];

export function AnswerSections({ sections }) {
  return (
    <div className="space-y-3">
      {sections.map((s, i) => (
        <div key={i} className="rounded-xl border border-slate-200/80 bg-white p-3.5">
          <div className="mb-2 flex items-center gap-2"><AIBadge type={s.label} /><span className="text-[13px] font-semibold text-[#071A2B]">{s.title}</span></div>
          <ul className="space-y-1 text-[13px] leading-relaxed text-slate-700">{s.lines.map((l, j) => <li key={j}>{l}</li>)}</ul>
        </div>
      ))}
    </div>
  );
}

export default function AIAssistant({ clientId }) {
  const { t, lang } = useApp();
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const ask = async (question) => {
    if (!question.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    try {
      const [r] = await Promise.all([api.post("/ai/ask", { client_id: clientId || null, question, lang }), new Promise((ok) => setTimeout(ok, 900))]);
      setMsgs((m) => [...m, { role: "ai", sections: r.data.sections }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "ai", sections: [{ label: "fact", title: "Error", lines: [errMsg(e)] }] }]);
    } finally { setBusy(false); }
  };

  return (
    <div className="flex h-full flex-col" data-testid="ai-assistant">
      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {!msgs.length && (
          <div className="grid gap-2 sm:grid-cols-2">
            {PROMPTS.map((p) => (
              <button key={p} onClick={() => ask(t(p))} data-testid={`ai-prompt-${p}`}
                className="group rounded-xl border border-slate-200 bg-white p-3 text-left text-[13px] text-slate-700 transition-colors hover:border-[#00A878]/60 hover:bg-emerald-50/40">
                <Sparkles className="mb-1.5 h-3.5 w-3.5 text-[#00A878] transition-transform group-hover:scale-110" />{t(p)}
              </button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={i} className="flex justify-end gap-2">
            <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-[#071A2B] px-4 py-2.5 text-[13px] text-white">{m.text}</div>
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200"><User className="h-3.5 w-3.5 text-slate-600" /></div>
          </div>
        ) : (
          <div key={i} className="flex gap-2" data-testid="ai-answer">
            <div className="ai-orb !h-7 !w-7 shrink-0"><Sparkles className="h-3 w-3 text-white" /></div>
            <div className="flex-1"><AnswerSections sections={m.sections} /></div>
          </div>
        ))}
        {busy && <AIThinking label={t("analyzing")} />}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="mt-4 flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-sm focus-within:ring-2 focus-within:ring-[#00A878]/30">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("ask_placeholder")} className="flex-1 bg-transparent px-3 py-2 text-sm outline-none" data-testid="ai-chat-input" />
        <button type="submit" disabled={busy} className="btn-emerald flex h-9 w-9 items-center justify-center rounded-xl disabled:opacity-50" data-testid="ai-chat-send"><SendHorizontal className="h-4 w-4" /></button>
      </form>
    </div>
  );
}
