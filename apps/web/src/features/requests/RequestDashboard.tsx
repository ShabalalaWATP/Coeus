import {
  CheckCircle2,
  ClipboardList,
  Hourglass,
  PackageOpen,
  Search,
  UsersRound,
} from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/ui/PageState";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import type { Ticket } from "../../lib/api-client/tickets";
import { ticketMetrics } from "./ticket-collection";

type RequestDashboardProps = {
  canCreate: boolean;
  onOpen: (ticketId: string) => void;
  tickets: Ticket[];
};

export function RequestDashboard({ canCreate, onOpen, tickets }: RequestDashboardProps) {
  const metrics = ticketMetrics(tickets);
  const metricItems = [
    { label: "Total requests", value: metrics.total, icon: ClipboardList, tone: "info" },
    { label: "Draft", value: metrics.draft, icon: Hourglass, tone: "warning" },
    { label: "Ready", value: metrics.ready, icon: CheckCircle2, tone: "success" },
    { label: "In progress", value: metrics.searching, icon: Search, tone: "info" },
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
          <h2 id="request-list-title">My requests</h2>
        </div>
        {tickets.length === 0 ? (
          <EmptyState
            hint={
              canCreate
                ? "Open a new request and the assistant will capture the details in chat."
                : "Requests shared with you appear here once you are tagged."
            }
            title="No requests yet"
          />
        ) : null}
        <div className="access-list">
          {tickets.map((ticket) => (
            <div className="access-row request-open-row" key={ticket.id}>
              <button
                className="request-open-row__main"
                onClick={() => onOpen(ticket.id)}
                type="button"
              >
                <span>{ticket.reference}</span>
                <strong>{ticket.intake.title ?? "Draft request"}</strong>
                <small>{formatWorkflowState(ticket.state)}</small>
                {ticket.collaborators.length > 0 ? (
                  <em className="request-open-row__shared">
                    <UsersRound aria-hidden="true" size={13} />
                    {ticket.collaborators.length} tagged
                  </em>
                ) : null}
              </button>
              {ticket.releasedProductIds.length > 0 ? (
                <Link
                  className="request-open-row__product"
                  state={{ from: "/app/requests" }}
                  to={`/store/products/${ticket.releasedProductIds[0]}`}
                >
                  <PackageOpen aria-hidden="true" size={15} />
                  View released product
                </Link>
              ) : null}
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
