import { ArrowUpRight, PackageCheck, PackageOpen, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/ui/PageState";
import { StatusPill } from "../../components/ui/StatusPill";
import type { Ticket, TicketSummary } from "../../lib/api-client/tickets";
import { isAwaitingCustomerAction, ticketMetrics } from "./ticket-collection";

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

  return (
    <>
      <section className="request-status-ledger" aria-label="Request summary">
        <div className="request-status-ledger__attention border-glow">
          <span>Needs your action</span>
          <strong>{metrics.awaitingAction}</strong>
          <small>Requests waiting for a decision or confirmation</small>
        </div>
        <dl>
          <div>
            <dt>Total</dt>
            <dd>{metrics.total}</dd>
          </div>
          <div>
            <dt>Draft</dt>
            <dd>{metrics.draft}</dd>
          </div>
          <div>
            <dt>Active</dt>
            <dd>{metrics.inProgress}</dd>
          </div>
          <div>
            <dt>Delivered</dt>
            <dd>{metrics.completed}</dd>
          </div>
        </dl>
      </section>

      <section className="surface request-list" aria-labelledby="request-list-title">
        <div className="request-list__heading">
          <div>
            <span>Request register</span>
            <h2 id="request-list-title">My requests</h2>
          </div>
          <p>Open a request to continue the conversation or review its progress.</p>
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
        <div className="request-register">
          {tickets.map((ticket) => {
            const requiresAction = isAwaitingCustomerAction(ticket.state);
            return (
              <article
                className={
                  requiresAction
                    ? "request-register-row request-register-row--action"
                    : "request-register-row"
                }
                key={ticket.id}
              >
                <button
                  className="request-register-row__main"
                  onClick={() => onOpen(ticket.id)}
                  type="button"
                >
                  <span className="mono-ref">{ticket.reference}</span>
                  <strong>{ticketTitle(ticket) ?? "Draft request"}</strong>
                  <div className="request-register-row__meta">
                    <StatusPill state={ticket.state} />
                    <span>{ticketPriority(ticket) ?? "Routine priority"}</span>
                    <time dateTime={ticket.updatedAt}>Updated {formatDate(ticket.updatedAt)}</time>
                    {collaboratorCount(ticket) > 0 ? (
                      <span>
                        <UsersRound aria-hidden="true" size={13} />
                        {collaboratorCount(ticket)} tagged
                      </span>
                    ) : null}
                  </div>
                  <span className="request-register-row__open">
                    Open
                    <ArrowUpRight aria-hidden="true" size={16} />
                  </span>
                </button>
                {releasedProductId(ticket) ? (
                  <Link
                    className="request-register-row__action"
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
                    className="request-register-row__action"
                    disabled={isConfirming}
                    onClick={() => onConfirmDelivery(ticket.id)}
                    type="button"
                  >
                    <PackageCheck aria-hidden="true" size={15} />
                    Confirm receipt and close
                  </button>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>
    </>
  );
}

function ticketTitle(ticket: Ticket | TicketSummary) {
  return "title" in ticket ? ticket.title : ticket.intake.title;
}

function ticketPriority(ticket: Ticket | TicketSummary) {
  return "priority" in ticket ? ticket.priority : ticket.intake.priority;
}

function collaboratorCount(ticket: Ticket | TicketSummary) {
  return "collaboratorCount" in ticket ? ticket.collaboratorCount : ticket.collaborators.length;
}

function releasedProductId(ticket: Ticket | TicketSummary) {
  return "releasedProductId" in ticket ? ticket.releasedProductId : ticket.releasedProductIds[0];
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}
