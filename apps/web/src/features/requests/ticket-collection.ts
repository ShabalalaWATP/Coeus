import type { TicketSummary } from "../../lib/api-client/tickets";

const CLOSED_TICKET_STATES = new Set<TicketSummary["state"]>([
  "CLOSED_DELIVERED",
  "CLOSED_REQUIREMENT_MET",
  "CLOSED_REANALYSIS_DECLINED",
  "CLOSED_EXISTING_PRODUCT_ACCEPTED",
  "CLOSED_UNANSWERED",
  "CLOSED_JOINED_EXISTING_WORK",
  "CANCELLED",
]);

export function ticketMetrics(
  tickets: Array<Pick<TicketSummary, "state"> & Partial<Pick<TicketSummary, "customerStatus">>>,
) {
  const draftStates = new Set(["DRAFT_INTAKE", "INFO_REQUIRED"]);
  const awaitingActionStates = new Set([
    "RFI_MATCH_OFFERED",
    "RFI_SEARCH_INCOMPLETE",
    "ACTIVE_WORK_REVIEW",
    "ACTIVE_WORK_SEARCH_INCOMPLETE",
    "NEW_TASKING_CONSENT",
    "COLLECT_CHOICE",
    "DISSEMINATION_READY",
  ]);
  return {
    total: tickets.length,
    draft: tickets.filter((ticket) => draftStates.has(ticket.state)).length,
    awaitingAction: tickets.filter(
      (ticket) => ticket.customerStatus?.actionRequired ?? awaitingActionStates.has(ticket.state),
    ).length,
    inProgress: tickets.filter(
      (ticket) =>
        !draftStates.has(ticket.state) &&
        !awaitingActionStates.has(ticket.state) &&
        !isClosedTicket(ticket.state),
    ).length,
    completed: tickets.filter((ticket) => isClosedTicket(ticket.state)).length,
  };
}

export function isClosedTicket(state: TicketSummary["state"]) {
  return CLOSED_TICKET_STATES.has(state);
}

export function isAwaitingCustomerAction(state: TicketSummary["state"]) {
  return new Set([
    "RFI_MATCH_OFFERED",
    "RFI_SEARCH_INCOMPLETE",
    "ACTIVE_WORK_REVIEW",
    "ACTIVE_WORK_SEARCH_INCOMPLETE",
    "NEW_TASKING_CONSENT",
    "COLLECT_CHOICE",
    "DISSEMINATION_READY",
  ]).has(state);
}
