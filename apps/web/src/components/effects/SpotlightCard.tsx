import type { ReactNode } from "react";

type SpotlightCardProps = {
  children: ReactNode;
  className?: string;
};

/**
 * Adapted from React Bits "Spotlight Card" (reactbits.dev) without extra
 * dependencies: pointer position is written to CSS custom properties and the
 * highlight itself is pure CSS, so reduced-motion users simply never hover.
 */
export function SpotlightCard({ children, className = "" }: SpotlightCardProps) {
  function handleMouseMove(event: React.MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
    event.currentTarget.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
  }

  return (
    <div className={`spotlight-card ${className}`.trim()} onMouseMove={handleMouseMove}>
      {children}
    </div>
  );
}
