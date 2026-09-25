export const BRAND = {
  iconDark: "/brand/finora-icon-dark.png",
  iconLight: "/brand/finora-icon-light.png",
  logoDark: "/brand/finora-logo-dark.png",
  logoLight: "/brand/finora-logo-light.png",
};

// light=true → placed on a dark surface (uses the dark app icon)
export function LogoMark({ size = 32, light = false }) {
  return (
    <img src={light ? BRAND.iconDark : BRAND.iconLight} alt="FINORA" width={size} height={size} data-testid="finora-logo-mark"
      className={`shrink-0 rounded-[24%] object-cover ${light ? "shadow-[0_0_18px_rgba(0,168,120,0.35)]" : "shadow-sm ring-1 ring-slate-200"}`} style={{ width: size, height: size }} />
  );
}

// Full logo (symbol + wordmark + tagline). dark=true for dark backgrounds.
export function LogoFull({ dark = false, className = "" }) {
  return <img src={dark ? BRAND.logoDark : BRAND.logoLight} alt="FINORA — Investment Management & Consulting Platform" data-testid="finora-logo-full"
    className={`select-none object-contain ${className}`} />;
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
