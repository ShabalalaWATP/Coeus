import type { Ticket } from "../../lib/api-client/tickets";

export function upsertTicket(tickets: Ticket[] | undefined, nextTicket: Ticket): Ticket[] {
  const current = tickets ?? [];
  if (current.some((ticket) => ticket.id === nextTicket.id)) {
    return current.map((ticket) => (ticket.id === nextTicket.id ? nextTicket : ticket));
  }
  return [nextTicket, ...current];
}

export function ticketMetrics(tickets: Ticket[]) {
  return {
    total: tickets.length,
    draft: tickets.filter((ticket) => ticket.state !== "RFI_SEARCHING").length,
    searching: tickets.filter((ticket) => ticket.state === "RFI_SEARCHING").length,
    ready: tickets.filter((ticket) => ticket.isReadyForSubmission).length,
  };
}
