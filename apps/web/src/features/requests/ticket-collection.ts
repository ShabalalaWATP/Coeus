import type { Ticket, TicketSummary } from "../../lib/api-client/tickets";

export function upsertTicket(tickets: Ticket[] | undefined, nextTicket: Ticket): Ticket[] {
  const current = tickets ?? [];
  if (current.some((ticket) => ticket.id === nextTicket.id)) {
    return current.map((ticket) => (ticket.id === nextTicket.id ? nextTicket : ticket));
  }
  return [nextTicket, ...current];
}

export function ticketMetrics(tickets: Array<Pick<TicketSummary, "state">>) {
  const draftStates = new Set(["DRAFT_INTAKE", "INFO_REQUIRED"]);
  const awaitingActionStates = new Set([
    "RFI_MATCH_OFFERED",
    "RFI_NO_MATCH",
    "COLLECT_CHOICE",
    "DISSEMINATION_READY",
  ]);
  const completedStates = new Set([
    "CLOSED_DELIVERED",
    "CLOSED_EXISTING_PRODUCT_ACCEPTED",
    "CANCELLED",
  ]);
  return {
    total: tickets.length,
    draft: tickets.filter((ticket) => draftStates.has(ticket.state)).length,
    awaitingAction: tickets.filter((ticket) => awaitingActionStates.has(ticket.state)).length,
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
    "RFI_NO_MATCH",
    "COLLECT_CHOICE",
    "DISSEMINATION_READY",
  ]).has(state);
}
