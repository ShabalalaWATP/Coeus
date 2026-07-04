const statusItems = [
  { label: "System Status", state: "Operational", tone: "success" },
  { label: "Data Services", state: "Operational", tone: "success" },
  { label: "Active Users", state: "-", tone: "neutral" },
  { label: "Local Time", state: "-", tone: "neutral" },
] as const;

export function StatusSummary() {
  return (
    <section className="status-strip" aria-label="Platform status">
      {statusItems.map((item) => (
        <div className="status-strip__item" key={item.label}>
          <span className={`status-dot status-dot--${item.tone}`} aria-hidden="true" />
          <span>{item.label}</span>
          <strong>{item.state}</strong>
        </div>
      ))}
    </section>
  );
}
