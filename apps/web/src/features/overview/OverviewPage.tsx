import { Activity, AlertTriangle, CheckCircle2, ClipboardList, Hourglass } from "lucide-react";

import { StatusSummary } from "../../components/status/StatusSummary";

const requestMetrics = [
  { label: "Total", value: "-", icon: ClipboardList, tone: "info" },
  { label: "Open", value: "-", icon: Hourglass, tone: "info" },
  { label: "At Risk", value: "-", icon: AlertTriangle, tone: "warning" },
  { label: "Overdue", value: "-", icon: AlertTriangle, tone: "critical" },
  { label: "Completed", value: "-", icon: CheckCircle2, tone: "success" },
] as const;

export default function OverviewPage() {
  return (
    <div className="overview-page">
      <section className="overview-hero" aria-labelledby="overview-title">
        <h1 id="overview-title">Requests</h1>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      <section className="request-metrics" aria-label="Request summary">
        {requestMetrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <article className="request-metric" key={metric.label}>
              <span className={`metric-icon metric-icon--${metric.tone}`} aria-hidden="true">
                <Icon size={22} strokeWidth={1.8} />
              </span>
              <div>
                <strong>{metric.value}</strong>
                <span>{metric.label}</span>
              </div>
            </article>
          );
        })}
      </section>
      <section className="request-workspace" aria-label="Request workspace">
        <article className="surface empty-request" aria-labelledby="empty-request-title">
          <ClipboardList aria-hidden="true" size={82} strokeWidth={1.3} />
          <h2 id="empty-request-title">No request selected</h2>
          <p>Select a request to view details.</p>
        </article>
        <aside className="surface activity-panel" aria-labelledby="activity-title">
          <h2 id="activity-title">Activity</h2>
          <div className="activity-panel__empty">
            <Activity aria-hidden="true" size={70} strokeWidth={1.3} />
            <p>No recent activity</p>
          </div>
        </aside>
      </section>
      <StatusSummary />
    </div>
  );
}
