import { Archive, ArrowUpRight, ChevronDown, PackageOpen, UsersRound } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/ui/PageState";
import { StatusPill } from "../../components/ui/StatusPill";
import type { Ticket, TicketSummary } from "../../lib/api-client/tickets";
import { RequestListControls, type RequestFilter } from "./RequestListControls";
import {
  groupOpenRequests,
  isAwaitingCustomerAction,
  isClosedTicket,
  requestGroupKey,
  sortRequests,
  ticketMetrics,
  type RequestSort,
} from "./ticket-collection";
import { ProductOutcomeDecisionPanel } from "./ProductOutcomeDecisionPanel";

type RequestDashboardProps = {
  canCreate: boolean;
  currentUserId: string;
  isDecidingOutcome: boolean;
  onProductDecision: (
    ticketId: string,
    meetsRequirement: boolean,
    reason: string,
    unmetCriteria: string[],
  ) => void;
  onOpen: (ticketId: string) => void;
  tickets: Array<Ticket | TicketSummary>;
};

export function RequestDashboard({
  canCreate,
  currentUserId,
  isDecidingOutcome,
  onProductDecision,
  onOpen,
  tickets,
}: RequestDashboardProps) {
  const [filter, setFilter] = useState<RequestFilter>("all");
  const [sort, setSort] = useState<RequestSort>("recent");
  const metrics = ticketMetrics(tickets);
  const openTickets = tickets.filter((ticket) => !isClosedTicket(ticket.state));
  const closedTickets = tickets.filter((ticket) => isClosedTicket(ticket.state));
  const groups = groupOpenRequests(openTickets, sort);
  const filterOptions = [
    { value: "all" as const, label: "All open", count: openTickets.length },
    ...groups.map((group) => ({
      value: group.key,
      label: group.title,
      count: group.tickets.length,
    })),
    { value: "closed" as const, label: "Closed", count: closedTickets.length },
  ];
  // A chosen category reads as one flat list; "all open" keeps the headings so
  // the shape of the workload is visible without picking anything.
  const selected =
    filter === "closed"
      ? sortRequests(closedTickets, sort)
      : filter === "all"
        ? []
        : sortRequests(
            openTickets.filter((ticket) => requestGroupKey(ticket) === filter),
            sort,
          );

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
            <dt>Open</dt>
            <dd>{metrics.total - metrics.completed}</dd>
          </div>
          <div>
            <dt>Draft</dt>
            <dd>{metrics.draft}</dd>
          </div>
          <div>
            <dt>In progress</dt>
            <dd>{metrics.inProgress}</dd>
          </div>
          <div>
            <dt>Closed</dt>
            <dd>{metrics.completed}</dd>
          </div>
        </dl>
      </section>

      <section className="surface request-list" aria-labelledby="request-list-title">
        <div className="request-list__heading">
          <div>
            <span>Request register</span>
            <h2 id="request-list-title">Your requests</h2>
          </div>
          <p>Grouped by what each one needs, with anything waiting on you first.</p>
        </div>
        {tickets.length > 0 ? (
          <RequestListControls
            filter={filter}
            onFilterChange={setFilter}
            onSortChange={setSort}
            options={filterOptions}
            sort={sort}
          />
        ) : null}
        {openTickets.length === 0 ? (
          <EmptyState
            hint={
              tickets.length > 0
                ? "Completed and cancelled requests are available in the closed section below."
                : canCreate
                  ? "Open a new request and the assistant will capture the details in chat."
                  : "Requests shared with you appear here once you are tagged."
            }
            title={tickets.length > 0 ? "No open requests" : "No requests yet"}
          />
        ) : null}
        {filter === "all" ? (
          groups.map((group) => (
            <section
              aria-labelledby={`request-group-${group.key}`}
              className="request-group"
              key={group.key}
            >
              <div className="request-group__heading">
                <h3 id={`request-group-${group.key}`}>
                  {group.title}
                  <span className="request-group__count">{group.tickets.length}</span>
                </h3>
                <p>{group.hint}</p>
              </div>
              <RequestRegister
                currentUserId={currentUserId}
                isDecidingOutcome={isDecidingOutcome}
                onOpen={onOpen}
                onProductDecision={onProductDecision}
                tickets={group.tickets}
              />
            </section>
          ))
        ) : (
          <RequestRegister
            currentUserId={currentUserId}
            isDecidingOutcome={isDecidingOutcome}
            onOpen={onOpen}
            onProductDecision={onProductDecision}
            tickets={selected}
          />
        )}
      </section>

      {filter === "all" && closedTickets.length > 0 ? (
        <details className="surface request-archive">
          <summary>
            <Archive aria-hidden="true" size={19} />
            <span>
              <strong>Closed requests</strong>
              <small>Completed and cancelled requests are kept here.</small>
            </span>
            <span className="request-archive__count">{closedTickets.length}</span>
            <ChevronDown aria-hidden="true" className="request-archive__chevron" size={19} />
          </summary>
          <RequestRegister
            currentUserId={currentUserId}
            isDecidingOutcome={isDecidingOutcome}
            onOpen={onOpen}
            onProductDecision={onProductDecision}
            tickets={sortRequests(closedTickets, sort)}
          />
        </details>
      ) : null}
    </>
  );
}

type RequestRegisterProps = Pick<
  RequestDashboardProps,
  "currentUserId" | "isDecidingOutcome" | "onOpen" | "onProductDecision" | "tickets"
>;

function RequestRegister({
  currentUserId,
  isDecidingOutcome,
  onOpen,
  onProductDecision,
  tickets,
}: RequestRegisterProps) {
  if (tickets.length === 0) return null;
  return (
    <div className="request-register">
      {tickets.map((ticket) => (
        <RequestRegisterRow
          currentUserId={currentUserId}
          isDecidingOutcome={isDecidingOutcome}
          key={ticket.id}
          onOpen={onOpen}
          onProductDecision={onProductDecision}
          ticket={ticket}
        />
      ))}
    </div>
  );
}

type RequestRegisterRowProps = Omit<RequestRegisterProps, "tickets"> & {
  ticket: Ticket | TicketSummary;
};

function RequestRegisterRow({
  currentUserId,
  isDecidingOutcome,
  onOpen,
  onProductDecision,
  ticket,
}: RequestRegisterRowProps) {
  const requiresAction =
    ticket.customerStatus?.actionRequired ?? isAwaitingCustomerAction(ticket.state);
  return (
    <article
      className={
        requiresAction
          ? "request-register-row request-register-row--action"
          : "request-register-row"
      }
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
          <span>{ticket.customerStatus?.label}</span>
          <span>{ticketPriority(ticket) ?? "Routine priority"}</span>
          <time dateTime={ticket.updatedAt}>Updated {formatDate(ticket.updatedAt)}</time>
          {collaboratorCount(ticket) > 0 ? (
            <span>
              <UsersRound aria-hidden="true" size={13} />
              {collaboratorCount(ticket)} tagged
            </span>
          ) : null}
        </div>
        {ticket.customerStatus ? (
          <small>
            {ticket.customerStatus.explanation} {formatEstimate(ticket.customerStatus)}
          </small>
        ) : null}
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
      {ticket.customerStatus?.canonicalTicketId ? (
        <Link
          className="request-register-row__action"
          to={`/app/requests/${encodeURIComponent(ticket.customerStatus.canonicalTicketId)}`}
        >
          <ArrowUpRight aria-hidden="true" size={15} />
          Track joined request
        </Link>
      ) : null}
      {ticket.state === "DISSEMINATION_READY" && ticket.requesterUserId === currentUserId ? (
        <ProductOutcomeDecisionPanel
          disabled={isDecidingOutcome}
          onDecide={(meetsRequirement, reason, unmetCriteria) =>
            onProductDecision(ticket.id, meetsRequirement, reason, unmetCriteria)
          }
        />
      ) : null}
    </article>
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

function formatEstimate(status: NonNullable<Ticket["customerStatus"]>) {
  const estimate = status.estimate;
  if (!estimate) return "";
  if (estimate.status === "paused") return "Estimate paused pending action.";
  if (!estimate.likely || !estimate.latest) return "Estimate available after routing.";
  return `Provisional delivery ${formatDate(estimate.likely)} to ${formatDate(estimate.latest)}.`;
}
