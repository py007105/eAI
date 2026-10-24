import { useEffect, useRef, useState } from "react";

const INT = /^-?\d+$/;

/** Shows `value` as given. When a purely numeric value changes to another number, counts from the old to
 * the new number (600 ms). Any other change renders the new value in the same render; non-numeric text is
 * shown unchanged; no animation under prefers-reduced-motion. Display only: the value always comes from the API. */
export default function NumberTicker({ value }: { value: string }) {
  const [frame, setFrame] = useState<string | null>(null);
  const prev = useRef(value);
  useEffect(() => {
    const before = prev.current;
    prev.current = value;
    const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!INT.test(before) || !INT.test(value) || before === value || reduce) {
      setFrame(null);
      return;
    }
    const from = Number(before);
    const to = Number(value);
    let raf = 0;
    const t0 = performance.now();
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / 600);
      const eased = 1 - Math.pow(1 - k, 3);
      if (k < 1) {
        setFrame(String(Math.round(from + (to - from) * eased)));
        raf = requestAnimationFrame(step);
      } else setFrame(null);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <span className="tabular">{frame ?? value}</span>;
}
