import { useEffect, useRef, useState } from "react";

/** Smoothly animates a number toward its latest value (count-up effect). */
export function useCountUp(target: number, duration = 900): number {
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);

  useEffect(() => {
    const from = fromRef.current;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const val = from + (target - from) * eased;
      setDisplay(val);
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return display;
}

export function NumberTicker({
  value,
  decimals = 0,
  className = "",
  suffix = "",
}: {
  value: number;
  decimals?: number;
  className?: string;
  suffix?: string;
}) {
  const v = useCountUp(value);
  return (
    <span className={className}>
      {v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
      {suffix}
    </span>
  );
}
