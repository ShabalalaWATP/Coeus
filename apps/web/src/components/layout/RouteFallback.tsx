export function RouteFallback() {
  return (
    <section className="surface surface--loading" aria-label="Loading route">
      <span className="loading-pulse" aria-hidden="true" />
      <p>Loading workspace</p>
    </section>
  );
}
