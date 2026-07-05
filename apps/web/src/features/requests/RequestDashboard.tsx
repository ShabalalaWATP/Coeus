import { CheckCircle2, ClipboardList, Hourglass, Search } from "lucide-react";

import type { Ticket } from "../../lib/api-client/tickets";
import { ticketMetrics } from "./ticket-collection";

type RequestDashboardProps = {
  onSelect: (ticketId: string) => void;
  selectedTicketId?: string;
  tickets: Ticket[];
};

export function RequestDashboard({ onSelect, selectedTicketId, tickets }: RequestDashboardProps) {
  const metrics = ticketMetrics(tickets);
  const metricItems = [
    { label: "Total", value: metrics.total, icon: ClipboardList, tone: "info" },
    { label: "Draft", value: metrics.draft, icon: Hourglass, tone: "warning" },
    { label: "Ready", value: metrics.ready, icon: CheckCircle2, tone: "success" },
    { label: "Searching", value: metrics.searching, icon: Search, tone: "info" },
  ] as const;

  return (
    <>
      <section className="request-metrics" aria-label="Request summary">
        {metricItems.map((metric) => {
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

      <section className="surface request-list" aria-labelledby="request-list-title">
        <div className="section-heading access-heading">
          <ClipboardList aria-hidden="true" size={20} />
          <h2 id="request-list-title">Tickets</h2>
        </div>
        {tickets.length === 0 ? <p>No tickets yet</p> : null}
        <div className="access-list">
          {tickets.map((ticket) => (
            <button
              className={
                ticket.id === selectedTicketId ? "access-row access-row--active" : "access-row"
              }
              key={ticket.id}
              onClick={() => onSelect(ticket.id)}
              type="button"
            >
              <span>{ticket.reference}</span>
              <strong>{ticket.intake.title ?? "Draft intake"}</strong>
              <small>{ticket.state.replaceAll("_", " ")}</small>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
