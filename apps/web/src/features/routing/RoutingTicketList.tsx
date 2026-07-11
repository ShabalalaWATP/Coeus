import { formatWorkflowState } from "../../lib/workflow/state-format";
import type { RoutingTicket } from "../../lib/api-client/routing";
import { formatTaggedReason } from "./routing-labels";

type RoutingTicketListProps = {
  disabled?: boolean;
  onSelect: (ticketId: string) => void;
  selectedTicketId?: string;
  tickets: RoutingTicket[];
};

export function RoutingTicketList({
  disabled = false,
  onSelect,
  selectedTicketId,
  tickets,
}: RoutingTicketListProps) {
  if (tickets.length === 0) {
    return <p>No tickets in this queue.</p>;
  }
  return (
    <>
      {tickets.map((ticket) => (
        <button
          className="request-row"
          aria-current={selectedTicketId === ticket.ticketId ? "true" : undefined}
          disabled={disabled}
          key={ticket.ticketId}
          onClick={() => onSelect(ticket.ticketId)}
          type="button"
        >
          <strong>{ticket.reference}</strong>
          <span>{ticket.title}</span>
          {ticket.priorityAssessment ? (
            <small
              className={`priority-badge priority-badge--${ticket.priorityAssessment.tier.toLowerCase()}`}
              aria-label={`${ticket.priorityAssessment.tier} priority. ${ticket.priorityAssessment.reasons.map(formatTaggedReason).join(". ")}`}
              title={ticket.priorityAssessment.reasons.map(formatTaggedReason).join(", ")}
            >
              {ticket.priorityAssessment.tier}
            </small>
          ) : null}
          <small>{formatWorkflowState(ticket.state)}</small>
        </button>
      ))}
    </>
  );
}
