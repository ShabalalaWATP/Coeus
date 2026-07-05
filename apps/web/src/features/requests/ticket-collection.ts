import type { Ticket } from "../../lib/api-client/tickets";

export function upsertTicket(tickets: Ticket[] | undefined, nextTicket: Ticket): Ticket[] {
  const current = tickets ?? [];
  if (current.some((ticket) => ticket.id === nextTicket.id)) {
    return current.map((ticket) => (ticket.id === nextTicket.id ? nextTicket : ticket));
  }
  return [nextTicket, ...current];
}

export function ticketMetrics(tickets: Ticket[]) {
  const searchingStates = new Set(["RFI_SEARCHING", "RFI_MATCH_OFFERED"]);
  const draftStates = new Set(["DRAFT_INTAKE", "INFO_REQUIRED"]);
  return {
    total: tickets.length,
    draft: tickets.filter((ticket) => draftStates.has(ticket.state)).length,
    searching: tickets.filter((ticket) => searchingStates.has(ticket.state)).length,
    ready: tickets.filter((ticket) => ticket.isReadyForSubmission).length,
  };
}
