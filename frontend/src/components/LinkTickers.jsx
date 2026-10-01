import { useEffect, useState } from "react";
import { Link2, Search } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";
import { Empty, Spinner } from "@/components/common";

function Row({ row, onLinked }) {
  const { t } = useApp();
  const [q, setQ] = useState(row.name || "");
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);

  const find = async () => {
    setBusy(true);
    const base = q.trim();
    const kws = [...new Set([base, base.replace(/[(（].*$/, "").trim(), base.replace(/[(（].*$/, "").trim().slice(0, 8)])].filter((k) => k.length >= 2);
    let found = [];
    for (const kw of kws) {
      try {
        const { data } = await api.get(`/quote/search?q=${encodeURIComponent(kw.slice(0, 40))}`);
        if (data.length) { found = data; break; }
      } catch (e) { toast.error(errMsg(e)); break; }
    }
    setItems(found);
    if (!found.length) toast.message(t("link_no_candidate"));
    setBusy(false);
  };

  const pick = async (tk) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/assets/prices/link?asset_id=${row.id}&ticker=${encodeURIComponent(tk)}`);
      toast.success(`${row.name} → ${data.ticker}${data.current_price ? ` · ${data.current_price}` : ""}`);
      onLinked(row.id);
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  return (
    <div className="border-b border-slate-100 py-3 last:border-0" data-testid={`unlinked-row-${row.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-[#071A2B]">{row.name}</span>
        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">{t(row.asset_class)}</span>
        {row.client_name && <span className="text-[11px] text-slate-500">{row.client_name}</span>}
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && find()} className="h-9 pl-9"
            placeholder={t("sec_placeholder")} data-testid={`unlinked-input-${row.id}`} />
        </div>
        <Button variant="outline" size="sm" className="h-9 shrink-0" disabled={busy || !q.trim()} onClick={find} data-testid={`unlinked-search-${row.id}`}>{t("link_search")}</Button>
      </div>
      {items.length > 0 && (
        <ul className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200">
          {items.map((it) => (
            <li key={it.ticker}>
              <button type="button" disabled={busy} onClick={() => pick(it.ticker)} data-testid={`unlinked-pick-${row.id}-${it.ticker}`}
                className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-emerald-50 disabled:opacity-50">
                <span className="w-20 shrink-0 font-num text-xs font-semibold text-[#071A2B]">{it.ticker}</span>
                <span className="min-w-0 flex-1 truncate text-slate-700">{it.name}</span>
                <span className="shrink-0 text-[10px] text-slate-400">{it.exchange}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function LinkTickers({ clientId, onChange }) {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState(null);

  const load = () => {
    setRows(null);
    api.get(`/assets/prices/unlinked${clientId ? `?client_id=${clientId}` : ""}`).then((r) => setRows(r.data)).catch(() => setRows([]));
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [clientId]);

  const linked = (id) => {
    setRows((p) => p.filter((r) => r.id !== id));
    onChange && onChange();
  };
  const n = (rows || []).length;

  return (
    <>
      <Button variant="outline" size="sm" className="h-8" onClick={() => { setOpen(true); load(); }} data-testid="link-tickers-btn">
        <Link2 className="mr-1 h-3.5 w-3.5" />{t("link_unlinked")}{n ? ` (${n})` : ""}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto" data-testid="link-tickers-dialog">
          <DialogHeader><DialogTitle className="font-display">{t("link_unlinked")}</DialogTitle></DialogHeader>
          <p className="text-xs text-slate-500">{t("link_hint")}</p>
          {rows === null ? <Spinner /> : rows.length === 0 ? <Empty text={t("link_all_done")} /> : rows.map((r) => <Row key={r.id} row={r} onLinked={linked} />)}
        </DialogContent>
      </Dialog>
    </>
  );
}
