import {
  CheckCircle2,
  ClipboardList,
  Hourglass,
  PackageCheck,
  PackageOpen,
  Search,
  UsersRound,
} from "lucide-react";
import { Link } from "react-router-dom";

import { CountUp } from "../../components/effects/CountUp";
import { SpotlightCard } from "../../components/effects/SpotlightCard";
import { EmptyState } from "../../components/ui/PageState";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import type { Ticket, TicketSummary } from "../../lib/api-client/tickets";
import { ticketMetrics } from "./ticket-collection";

type RequestDashboardProps = {
  canCreate: boolean;
  currentUserId: string;
  isConfirming: boolean;
  onConfirmDelivery: (ticketId: string) => void;
  onOpen: (ticketId: string) => void;
  tickets: Array<Ticket | TicketSummary>;
};

export function RequestDashboard({
  canCreate,
  currentUserId,
  isConfirming,
  onConfirmDelivery,
  onOpen,
  tickets,
}: RequestDashboardProps) {
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
            <SpotlightCard className="request-metric" key={metric.label}>
              <span className={`metric-icon metric-icon--${metric.tone}`} aria-hidden="true">
                <Icon size={22} strokeWidth={1.8} />
              </span>
              <div>
                <strong>
                  <CountUp value={metric.value} />
                </strong>
                <span>{metric.label}</span>
              </div>
            </SpotlightCard>
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
                <strong>{ticketTitle(ticket) ?? "Draft request"}</strong>
                <small>{formatWorkflowState(ticket.state)}</small>
                {collaboratorCount(ticket) > 0 ? (
                  <em className="request-open-row__shared">
                    <UsersRound aria-hidden="true" size={13} />
                    {collaboratorCount(ticket)} tagged
                  </em>
                ) : null}
              </button>
              {releasedProductId(ticket) ? (
                <Link
                  className="request-open-row__product"
                  state={{ from: "/app/requests" }}
                  to={`/store/products/${encodeURIComponent(releasedProductId(ticket) ?? "")}`}
                >
                  <PackageOpen aria-hidden="true" size={15} />
                  View released product
                </Link>
              ) : null}
              {ticket.state === "DISSEMINATION_READY" &&
              ticket.requesterUserId === currentUserId ? (
                <button
                  className="request-open-row__product"
                  disabled={isConfirming}
                  onClick={() => onConfirmDelivery(ticket.id)}
                  type="button"
                >
                  <PackageCheck aria-hidden="true" size={15} />
                  Confirm receipt and close
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function ticketTitle(ticket: Ticket | TicketSummary) {
  return "title" in ticket ? ticket.title : ticket.intake.title;
}

function collaboratorCount(ticket: Ticket | TicketSummary) {
  return "collaboratorCount" in ticket ? ticket.collaboratorCount : ticket.collaborators.length;
}

function releasedProductId(ticket: Ticket | TicketSummary) {
  return "releasedProductId" in ticket ? ticket.releasedProductId : ticket.releasedProductIds[0];
}
