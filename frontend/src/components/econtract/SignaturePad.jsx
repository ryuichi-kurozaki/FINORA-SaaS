import { useEffect, useRef } from "react";

export default function SignaturePad({ onChange, t }) {
  const ref = useRef(null);
  const drawing = useRef(false);
  const dirty = useRef(false);
  useEffect(() => {
    const c = ref.current;
    const r = c.getBoundingClientRect();
    c.width = r.width * 2; c.height = r.height * 2;
    const x = c.getContext("2d");
    x.scale(2, 2); x.lineWidth = 2.2; x.lineCap = "round"; x.strokeStyle = "#071A2B";
  }, []);
  const pos = (e) => { const r = ref.current.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  const down = (e) => { drawing.current = true; const x = ref.current.getContext("2d"); x.beginPath(); x.moveTo(...pos(e)); ref.current.setPointerCapture(e.pointerId); };
  const move = (e) => { if (!drawing.current) return; const x = ref.current.getContext("2d"); x.lineTo(...pos(e)); x.stroke(); dirty.current = true; };
  const up = () => { if (!drawing.current) return; drawing.current = false; if (dirty.current) onChange(ref.current.toDataURL("image/png")); };
  const clear = () => { const c = ref.current; c.getContext("2d").clearRect(0, 0, c.width, c.height); dirty.current = false; onChange(""); };
  return (
    <div>
      <canvas ref={ref} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerLeave={up}
        className="h-36 w-full touch-none rounded-xl border-2 border-dashed border-slate-300 bg-white" data-testid="ec-signature-pad" />
      <button type="button" onClick={clear} className="mt-1 text-xs text-slate-500 underline" data-testid="ec-signature-clear">{t("ec_clear_sign")}</button>
    </div>
  );
}
