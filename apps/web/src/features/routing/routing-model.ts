import type { RoutingRoute, RoutingTicket } from "../../lib/api-client/routing";

// JIOC decides routes: actions are available while the ticket awaits a
// JIOC decision, regardless of which route the decision will pick.
export function canApprove(ticket: RoutingTicket) {
  return (
    ticket.state === "JIOC_REVIEW" &&
    ticket.rfaReview !== null &&
    ticket.cmReview !== null &&
    ticket.recommendation !== null
  );
}

function canReviewDecision(ticket: RoutingTicket) {
  return ticket.state === "JIOC_REVIEW";
}

export function canReject(ticket: RoutingTicket, reason: string) {
  return canReviewDecision(ticket) && reason.trim().length >= 3;
}

export function canSubmitClarification(ticket: RoutingTicket, reason: string, question: string) {
  return canReviewDecision(ticket) && reason.trim().length >= 3 && question.trim().length >= 3;
}

/**
 * Approving a route that the orchestrator did not recommend is an override
 * and requires a recorded reason from the JIOC reviewer.
 */
export function isRouteOverride(ticket: RoutingTicket, route: RoutingRoute) {
  return ticket.recommendation !== null && ticket.recommendation.recommendedRoute !== route;
}

export function canApproveWithOverride(
  ticket: RoutingTicket,
  route: RoutingRoute,
  overrideReason: string,
) {
  if (!canApprove(ticket)) {
    return false;
  }
  return !isRouteOverride(ticket, route) || overrideReason.trim().length >= 3;
}

export function upsertRoutingTicket(tickets: RoutingTicket[], nextTicket: RoutingTicket) {
  const shouldRemainVisible =
    nextTicket.state === "JIOC_REVIEW" || nextTicket.state === "COLLECT_CHOICE";
  const withoutCurrent = tickets.filter((ticket) => ticket.ticketId !== nextTicket.ticketId);
  return shouldRemainVisible ? [nextTicket, ...withoutCurrent] : withoutCurrent;
}
