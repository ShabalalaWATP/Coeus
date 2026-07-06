import type { RoutingRoute, RoutingTicket } from "../../lib/api-client/routing";

export function canApprove(ticket: RoutingTicket, route: RoutingRoute) {
  return ticket.state === (route === "rfa" ? "RFA_MANAGER_REVIEW" : "CM_MANAGER_REVIEW");
}

export function canReject(ticket: RoutingTicket, route: RoutingRoute, reason: string) {
  return canApprove(ticket, route) && reason.trim().length >= 3;
}

export function canSubmitClarification(ticket: RoutingTicket, route: RoutingRoute, reason: string) {
  return canApprove(ticket, route) && reason.trim().length >= 3;
}

export function upsertRoutingTicket(
  tickets: RoutingTicket[],
  nextTicket: RoutingTicket,
  route: RoutingRoute,
) {
  const visibleState = route === "rfa" ? "RFA_MANAGER_REVIEW" : "CM_MANAGER_REVIEW";
  const shouldRemainVisible =
    nextTicket.state === visibleState ||
    nextTicket.state === "ROUTE_ASSESSMENT" ||
    nextTicket.state === "ANALYST_ASSIGNMENT";
  const withoutCurrent = tickets.filter((ticket) => ticket.ticketId !== nextTicket.ticketId);
  return shouldRemainVisible ? [nextTicket, ...withoutCurrent] : withoutCurrent;
}
