import { formatWorkflowState } from "../../lib/workflow/state-format";
import type { RoutingTicket } from "../../lib/api-client/routing";

type RoutingTicketListProps = {
  onSelect: (ticketId: string) => void;
  tickets: RoutingTicket[];
};

export function RoutingTicketList({ onSelect, tickets }: RoutingTicketListProps) {
  if (tickets.length === 0) {
    return <p>No tickets in this queue.</p>;
  }
  return (
    <>
      {tickets.map((ticket) => (
        <button
          className="request-row"
          key={ticket.ticketId}
          onClick={() => onSelect(ticket.ticketId)}
          type="button"
        >
          <strong>{ticket.reference}</strong>
          <span>{ticket.title}</span>
          {ticket.priorityAssessment ? (
            <small
              className={`priority-badge priority-badge--${ticket.priorityAssessment.tier.toLowerCase()}`}
              title={ticket.priorityAssessment.reasons.join(", ")}
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
