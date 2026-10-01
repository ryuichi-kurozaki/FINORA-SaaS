import { useEffect, useRef, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import { api, errMsg } from "@/lib/api";
import { CURRENCIES } from "@/config/entities";

function Results({ items, hi, onPick }) {
  const { t } = useApp();
  return (
    <ul className="absolute left-0 right-0 top-full z-50 mt-1 max-h-96 overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-lg" data-testid="security-search-results">
      {items.map((it, i) => (
        <li key={it.ticker}>
          <button type="button" onMouseDown={(e) => { e.preventDefault(); onPick(it); }} data-testid={`security-result-${it.ticker}`}
            className={`flex w-full flex-col items-start gap-1 px-3 py-2 text-left text-sm transition-colors ${i === hi ? "bg-emerald-50" : "hover:bg-slate-50"}`}>
            <span className="w-full whitespace-normal break-words leading-snug text-slate-800">{it.name}</span>
            <span className="flex w-full flex-wrap items-center gap-2 text-[11px] text-slate-500">
              <span className="font-num font-semibold text-[#071A2B]">{it.ticker}</span>
              <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">{t(it.asset_class)}</span>
              {it.exchange && <span>{it.exchange}</span>}
              {it.price != null && <span className="font-num">{it.price.toLocaleString("ja-JP")}{it.price_unit > 1 ? ` / ${it.price_unit.toLocaleString("ja-JP")}口` : ""}</span>}
              {it.price_date && <span className="font-num text-slate-400">{it.price_date}</span>}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function SecuritySearch({ form, set }) {
  const { t } = useApp();
  const [q, setQ] = useState(form.ticker || "");
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(-1);
  const [busy, setBusy] = useState(false);
  const skip = useRef(true);

  useEffect(() => {
    if (skip.current) { skip.current = false; return undefined; }
    const s = q.trim();
    if (!s) { setItems([]); return undefined; }
    const id = setTimeout(() => api.get(`/quote/search?q=${encodeURIComponent(s)}`).then((r) => { setItems(r.data); setHi(-1); setOpen(true); }).catch(() => setItems([])), 300);
    return () => clearTimeout(id);
  }, [q]);

  const fill = (x) => {
    ["ticker", "name", "asset_class"].forEach((k) => x[k] && set(k, x[k]));
    set("price_unit", x.price_unit ? String(x.price_unit) : "");
    if (x.country) set("country", x.country);
    if (x.sector && !form.sector) set("sector", x.sector);
    if (x.currency && CURRENCIES.includes(x.currency)) set("currency", x.currency);
  };
  const lookup = async (ticker, base) => {
    setBusy(true); setOpen(false);
    if (base) fill(base);
    try {
      const { data: x } = await api.get(`/quote?ticker=${encodeURIComponent(ticker)}`);
      fill(x); set("current_price", x.price); set("price_date", x.price_date);
      skip.current = true; setQ(`${x.ticker} ${x.name}`);
      toast.success(`${x.name} · ${x.price} ${x.currency || ""}`);
    } catch (e) { if (!base) toast.error(errMsg(e)); else toast.message(t("sec_no_price")); }
    setBusy(false);
  };
  const pick = (it) => { skip.current = true; setQ(`${it.ticker} ${it.name}`); lookup(it.ticker, it); };
  const onKey = (e) => {
    if (e.key === "ArrowDown" && items.length) { e.preventDefault(); setOpen(true); setHi((h) => Math.min(h + 1, items.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    if (e.key === "Escape") setOpen(false);
    if (e.key === "Enter") { e.preventDefault(); if (open && hi >= 0) pick(items[hi]); else if (q.trim()) lookup(q.trim().split(" ")[0]); }
  };

  return (
    <div className="rounded-xl border border-[#00A878]/30 bg-emerald-50/40 p-3" data-testid="security-search">
      <span className="mb-1.5 block text-xs font-semibold text-[#071A2B]">{t("sec_search")}</span>
      <div className="relative flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} onFocus={() => items.length && setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
            placeholder={t("sec_placeholder")} className="h-10 bg-white pl-9" autoComplete="off" data-testid="security-search-input" />
          {open && items.length > 0 && <Results items={items} hi={hi} onPick={pick} />}
        </div>
        <Button type="button" variant="outline" className="h-10 shrink-0 bg-white" disabled={!q.trim() || busy} onClick={() => lookup(q.trim().split(" ")[0])} data-testid="ticker-lookup-btn">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : t("ticker_lookup")}
        </Button>
      </div>
      <p className="mt-1.5 text-[11px] text-slate-500">{t("sec_hint")}</p>
    </div>
  );
}
