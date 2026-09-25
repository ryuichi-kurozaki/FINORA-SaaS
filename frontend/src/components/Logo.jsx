export function LogoMark({ size = 32, light = false }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="fg" x1="0" y1="40" x2="40" y2="0">
          <stop offset="0" stopColor="#00A878" />
          <stop offset="1" stopColor="#5FE0B8" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="38" height="38" rx="11" fill={light ? "rgba(255,255,255,0.06)" : "#071A2B"} stroke="rgba(0,168,120,0.45)" />
      <path d="M12 30V11h15" stroke="url(#fg)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 20h9" stroke="url(#fg)" strokeWidth="3.2" strokeLinecap="round" />
      <path d="M21 29l4-5 3 2 4-7" stroke="#C9A227" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="32" cy="19" r="2" fill="#C9A227" />
      <circle cx="27" cy="11" r="1.6" fill="#5FE0B8" />
    </svg>
  );
}

export function Logo({ light = false, size = 32, tagline = false }) {
  return (
    <div className="flex items-center gap-3" data-testid="finora-logo">
      <LogoMark size={size} light={light} />
      <div className="leading-none">
        <div className="font-display text-[22px] font-extrabold tracking-[0.14em]">
          <span className={light ? "text-white" : "text-[#071A2B]"}>FIN</span>
          <span className="text-[#00A878]">ORA</span>
        </div>
        {tagline && <div className={`mt-1 whitespace-nowrap text-[8.5px] tracking-[0.16em] uppercase ${light ? "text-slate-400" : "text-slate-500"}`}>Investment Intelligence</div>}
      </div>
    </div>
  );
}
