import { useEffect, useState } from "react";

import { prefersReducedMotion } from "./motion-preference";

type CountUpProps = {
  value: number;
  durationMs?: number;
};

/**
 * Adapted from React Bits "Count Up" (reactbits.dev) using requestAnimationFrame
 * instead of a motion dependency. Renders the final value immediately for
 * reduced-motion users and in environments without matchMedia (tests).
 */
export function CountUp({ durationMs = 700, value }: CountUpProps) {
  const [display, setDisplay] = useState(() => (prefersReducedMotion() ? value : 0));

  useEffect(() => {
    if (prefersReducedMotion()) {
      setDisplay(value);
      return undefined;
    }
    const start = performance.now();
    let frame = requestAnimationFrame(function tick(now: number) {
      const progress = Math.min((now - start) / durationMs, 1);
      const eased = 1 - (1 - progress) ** 3;
      setDisplay(Math.round(value * eased));
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [durationMs, value]);

  return <>{display}</>;
}
