import { useEffect, useState } from "react";
import { useCountUp } from "../lib/motion";

const R = 18;
const C = 2 * Math.PI * R;

/** Кольцо уверенности: дуга дорисовывается, число считается до значения. */
export function Ring({ value, label, size = 52 }: { value: number; label?: string; size?: number }) {
  const v = Math.max(0, Math.min(1, value || 0));
  const [ready, setReady] = useState(false);
  const shown = Math.round(useCountUp(v * 100, 900));
  useEffect(() => {
    const id = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const tone = v >= 0.75 ? "high" : v >= 0.5 ? "mid" : "low";
  return (
    <div className={`ring ring-${tone}`} style={{ width: size, height: size }} role="img" aria-label={`${label ?? "Уверенность"}: ${Math.round(v * 100)}%`}>
      <svg viewBox="0 0 44 44" aria-hidden="true">
        <circle className="ring-track" cx="22" cy="22" r={R} />
        <circle className="ring-arc" cx="22" cy="22" r={R} strokeDasharray={C} strokeDashoffset={ready ? C * (1 - v) : C} transform="rotate(-90 22 22)" />
      </svg>
      <span className="tabnum" aria-hidden="true">
        {shown}
      </span>
    </div>
  );
}
