export const yen = (v) => (v == null || isNaN(v) ? "—" : `¥${Math.round(v).toLocaleString("ja-JP")}`);

export const num = (v, d = 0) => (v == null || isNaN(v) ? "—" : Number(v).toLocaleString("ja-JP", { maximumFractionDigits: d }));

export const pct = (v, sign = true) => (v == null || isNaN(v) ? "—" : `${sign && v > 0 ? "+" : ""}${Number(v).toFixed(1)}%`);

export function compact(v, lang = "ja") {
  if (v == null || isNaN(v)) return "—";
  const a = Math.abs(v), s = v < 0 ? "-" : "";
  if (lang === "ja") {
    if (a >= 1e8) return `${s}¥${(a / 1e8).toFixed(2)}億`;
    if (a >= 1e4) return `${s}¥${Math.round(a / 1e4).toLocaleString("ja-JP")}万`;
    return `${s}¥${Math.round(a)}`;
  }
  return `${s}¥${new Intl.NumberFormat(lang === "pt" ? "pt-BR" : "en-US", { notation: "compact", maximumFractionDigits: 2 }).format(a)}`;
}

export const fmtDate = (s) => (s ? String(s).slice(0, 10) : "—");
export const fmtDateTime = (s) => (s ? String(s).replace("T", " ").slice(0, 19) : "—");
export const bytes = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
export const plColor = (v) => (v > 0 ? "text-[#00A878]" : v < 0 ? "text-red-600" : "text-slate-600");
