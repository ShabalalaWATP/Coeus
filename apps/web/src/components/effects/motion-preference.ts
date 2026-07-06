/**
 * JS-driven effects check reduced-motion themselves because the global CSS
 * kill switch cannot stop canvas or rAF work. Environments without matchMedia
 * (jsdom) are treated as reduced so tests stay deterministic.
 */
export function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? true;
}
