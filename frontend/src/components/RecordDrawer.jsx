import { MessageSquareWarning } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useApp } from "@/context/AppContext";
import { fmtDateTime } from "@/lib/format";
import CommentThread from "@/components/CommentThread";

const HIDE = ["id", "tenant_id", "client_id", "created_by", "updated_by", "_userName", "account_id", "asset_id", "owner_id"];

export default function RecordDrawer({ row, entity, onClose, onCorrection }) {
  const { t, isClient } = useApp();
  if (!row) return null;
  const label = row.name || row.institution || row.title || row.tx_type;
  const entries = Object.entries(row).filter(([k, v]) => !HIDE.includes(k) && v !== null && v !== "" && typeof v !== "object");
  return (
    <Sheet open={!!row} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto bg-[#F7F9FC] sm:max-w-lg" data-testid="record-drawer">
        <SheetHeader><SheetTitle className="font-display">{t(entity)} · {label}</SheetTitle></SheetHeader>
        <div className="mt-2 text-[11px] text-slate-500" data-testid="record-provenance">
          {t("last_updated")}: <span className="font-num">{fmtDateTime(row.updated_at)}</span> · {t("source")}: {t(row.source || "MANUAL")} · {row.updated_by_role ? t(row.updated_by_role === "client" ? "client_role" : row.updated_by_role) : "—"}
        </div>
        <dl className="mt-4 grid grid-cols-[130px_1fr] gap-x-3 gap-y-2 rounded-xl bg-white p-4 text-sm shadow-sm">
          {entries.map(([k, v]) => <div key={k} className="contents"><dt className="text-xs text-slate-500">{t(k)}</dt><dd className="break-words font-num text-slate-800">{typeof v === "number" ? v.toLocaleString("ja-JP", { maximumFractionDigits: 4 }) : String(v)}</dd></div>)}
        </dl>
        {!isClient && onCorrection && (
          <button onClick={() => onCorrection(row)} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-[#C9A227]/50 bg-[#C9A227]/10 px-4 py-2.5 text-sm font-semibold text-[#8a6d12]" data-testid="drawer-correction-btn">
            <MessageSquareWarning className="h-4 w-4" />{t("request_correction")}
          </button>
        )}
        <div className="mt-5 rounded-xl bg-white p-4 shadow-sm"><CommentThread clientId={row.client_id} targetType={entity} targetId={row.id} targetLabel={label} /></div>
      </SheetContent>
    </Sheet>
  );
}
