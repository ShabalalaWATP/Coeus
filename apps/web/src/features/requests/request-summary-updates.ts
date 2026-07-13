import type { InfiniteData, QueryClient } from "@tanstack/react-query";

import type { Ticket, TicketSummary, TicketSummaryPage } from "../../lib/api-client/tickets";

export function withAcceptedProduct(current: string[], acceptedProductId: string | null) {
  if (acceptedProductId === null || current.includes(acceptedProductId)) {
    return current;
  }
  return [...current, acceptedProductId];
}

export function updateTicketSummary(queryClient: QueryClient, summary: TicketSummary) {
  queryClient.setQueryData<InfiniteData<TicketSummaryPage>>(["tickets"], (current) => {
    if (!current) return current;
    let found = false;
    const pages = current.pages.map((page) => ({
      ...page,
      tickets: page.tickets.map((ticket) => {
        if (ticket.id !== summary.id) return ticket;
        found = true;
        return summary;
      }),
    }));
    if (!found && pages[0]) pages[0] = { ...pages[0], tickets: [summary, ...pages[0].tickets] };
    return { ...current, pages };
  });
}

export function updateTicketSummaryState(
  queryClient: QueryClient,
  ticketId: string,
  state: Ticket["state"],
  releasedProductId: string | null,
) {
  queryClient.setQueryData<InfiniteData<TicketSummaryPage>>(["tickets"], (current) =>
    current
      ? {
          ...current,
          pages: current.pages.map((page) => ({
            ...page,
            tickets: page.tickets.map((ticket) =>
              ticket.id === ticketId
                ? {
                    ...ticket,
                    state,
                    releasedProductId: releasedProductId ?? ticket.releasedProductId,
                  }
                : ticket,
            ),
          })),
        }
      : current,
  );
}

export function ticketSummary(ticket: Ticket): TicketSummary {
  return {
    id: ticket.id,
    reference: ticket.reference,
    requesterUserId: ticket.requesterUserId,
    state: ticket.state,
    title: ticket.intake.title,
    priority: ticket.intake.priority,
    isReadyForSubmission: ticket.isReadyForSubmission,
    collaboratorCount: ticket.collaborators.length,
    releasedProductId: ticket.releasedProductIds[0] ?? null,
    createdAt: ticket.createdAt,
    updatedAt: ticket.updatedAt,
  };
}
