import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApp } from "@/context/AppContext";
import { compact, yen } from "@/lib/format";

export const COLORS = ["#00A878", "#0B3A5B", "#C9A227", "#5FD4B0", "#1F6F8B", "#8CA3B8", "#E4C865", "#2F855A", "#A0AEC0", "#123047"];

function Tip({ active, payload, label, fmt = yen }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#071A2B]/95 px-3 py-2 text-xs text-white shadow-xl backdrop-blur">
      {label != null && <div className="mb-1 text-slate-400">{label}</div>}
      {payload.map((p) => (
        <div key={p.dataKey || p.name} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.payload?.fill }} />
          <span className="text-slate-300">{p.name}</span>
          <span className="ml-auto font-num">{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function Donut({ data, height = 230, testid }) {
  const { t, lang } = useApp();
  const rows = (data || []).map((d) => ({ ...d, name: t(d.key) }));
  if (!rows.length) return <div className="py-16 text-center text-sm text-slate-400">{t("no_data")}</div>;
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row" data-testid={testid}>
      <div className="h-[200px] w-full sm:w-1/2" style={{ height }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={rows} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="92%" paddingAngle={2} stroke="none" animationDuration={900}>
              {rows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip content={<Tip fmt={(v) => compact(v, lang)} />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="w-full space-y-1.5 sm:w-1/2">
        {rows.slice(0, 7).map((r, i) => (
          <li key={r.key} className="flex items-center gap-2 text-xs">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} />
            <span className="truncate text-slate-600">{r.name}</span>
            <span className="ml-auto font-num font-medium text-[#071A2B]">{r.pct}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const axis = { fontSize: 11, fill: "#718096" };

export function TrendChart({ data, keys, height = 280, testid }) {
  const { t, lang } = useApp();
  return (
    <div style={{ height }} data-testid={testid}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
          <defs>
            {keys.map((k, i) => (
              <linearGradient key={k} id={`g-${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor={COLORS[i]} stopOpacity={0.28} />
                <stop offset="1" stopColor={COLORS[i]} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke="#EDF2F7" vertical={false} />
          <XAxis dataKey="date" tick={axis} tickLine={false} axisLine={false} minTickGap={24} />
          <YAxis tick={axis} tickLine={false} axisLine={false} tickFormatter={(v) => compact(v, lang)} width={78} />
          <Tooltip content={<Tip fmt={(v) => compact(v, lang)} />} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
          {keys.map((k, i) => (
            <Area key={k} type="monotone" dataKey={k} name={t(k)} stroke={COLORS[i]} strokeWidth={2} fill={`url(#g-${k})`} animationDuration={1200} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function LinesChart({ data, x = "date", lines, height = 280, testid }) {
  const { lang } = useApp();
  return (
    <div style={{ height }} data-testid={testid}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
          <CartesianGrid stroke="#EDF2F7" vertical={false} />
          <XAxis dataKey={x} tick={axis} tickLine={false} axisLine={false} minTickGap={20} />
          <YAxis tick={axis} tickLine={false} axisLine={false} tickFormatter={(v) => compact(v, lang)} width={78} />
          <Tooltip content={<Tip fmt={(v) => compact(v, lang)} />} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
          {lines.map((l) => (
            <Line key={l.key} type="monotone" dataKey={l.key} name={l.name} stroke={l.color} strokeWidth={l.width || 2.2} strokeDasharray={l.dash} dot={false} animationDuration={1200} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function HBars({ data, height = 240, color = "#00A878", testid }) {
  const { t, lang } = useApp();
  const rows = (data || []).map((d) => ({ ...d, name: t(d.key) }));
  if (!rows.length) return <div className="py-16 text-center text-sm text-slate-400">{t("no_data")}</div>;
  return (
    <div style={{ height }} data-testid={testid}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={110} tick={axis} tickLine={false} axisLine={false} />
          <Tooltip content={<Tip fmt={(v) => compact(v, lang)} />} cursor={{ fill: "rgba(0,168,120,0.06)" }} />
          <Bar dataKey="value" name={t("amount")} radius={[0, 6, 6, 0]} fill={color} animationDuration={1000} barSize={14} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function IncomeExpense({ cf, height = 240 }) {
  const { t, lang } = useApp();
  const rows = [{ name: t("monthly_cf"), income: cf.income_m, expense: cf.expense_m, free: cf.free_m }];
  return (
    <div style={{ height }} data-testid="chart-income-expense">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 8 }}>
          <CartesianGrid stroke="#EDF2F7" vertical={false} />
          <XAxis dataKey="name" tick={axis} tickLine={false} axisLine={false} />
          <YAxis tick={axis} tickLine={false} axisLine={false} tickFormatter={(v) => compact(v, lang)} width={78} />
          <Tooltip content={<Tip fmt={(v) => compact(v, lang)} />} cursor={{ fill: "rgba(0,168,120,0.05)" }} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
          <Bar dataKey="income" name={t("income")} fill="#00A878" radius={[6, 6, 0, 0]} barSize={46} />
          <Bar dataKey="expense" name={t("expense")} fill="#0B3A5B" radius={[6, 6, 0, 0]} barSize={46} />
          <Bar dataKey="free" name={t("free_cash")} fill="#C9A227" radius={[6, 6, 0, 0]} barSize={46} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProjectionChart({ rows, height = 280, testid = "chart-projection" }) {
  const { t } = useApp();
  return (
    <LinesChart data={rows} x="year" height={height} testid={testid} lines={[
      { key: "bull", name: t("bull"), color: "#00A878" },
      { key: "base", name: t("base"), color: "#0B3A5B", width: 2.8 },
      { key: "bear", name: t("bear"), color: "#C9A227" },
      { key: "principal", name: t("contributed"), color: "#A0AEC0", dash: "4 4", width: 1.5 },
    ]} />
  );
}
