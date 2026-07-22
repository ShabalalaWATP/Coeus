import type { TicketSummary } from "../../lib/api-client/tickets";

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
  const completedStates = new Set([
    "CLOSED_DELIVERED",
    "CLOSED_EXISTING_PRODUCT_ACCEPTED",
    "CLOSED_UNANSWERED",
    "CLOSED_JOINED_EXISTING_WORK",
    "CANCELLED",
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
        !completedStates.has(ticket.state),
    ).length,
    completed: tickets.filter((ticket) => completedStates.has(ticket.state)).length,
  };
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
