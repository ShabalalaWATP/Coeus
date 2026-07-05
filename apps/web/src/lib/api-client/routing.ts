import { resolveApiBaseUrl, toApiError } from "./client";
import type { TicketState } from "./tickets";

export type RoutingRoute = "rfa" | "cm";

export type CapabilityReview = {
  id: string;
  canSatisfy: boolean;
  confidence: number;
  requiredClarifications: string[];
  estimatedEffort: string;
  risks: string[];
  managerReviewRequired: boolean;
  reasoningSummary: string;
  createdAt: string;
};

export type RfaCapabilityReview = CapabilityReview & {
  suggestedWorkPackages: string[];
  suggestedTeamId: string | null;
};

export type CmCapabilityReview = CapabilityReview & {
  suggestedCollectionRoute: string | null;
  suggestedCollectionSources: string[];
};

export type RouteRecommendation = {
  id: string;
  recommendedRoute: "rfa" | "cm" | "clarification";
  reasoningSummary: string;
  createdAt: string;
};

export type RoutingTicket = {
  ticketId: string;
  reference: string;
  requesterUserId: string;
  state: TicketState;
  title: string;
  priority: string | null;
  rfaReview: RfaCapabilityReview | null;
  cmReview: CmCapabilityReview | null;
  recommendation: RouteRecommendation | null;
  clarifications: {
    id: string;
    route: string;
    reason: string;
    questions: string[];
    requestedByUserId: string;
    createdAt: string;
  }[];
  managerDecisions: {
    id: string;
    route: string;
    status: string;
    reason: string;
    overrideReason: string | null;
    actorUserId: string;
    createdAt: string;
  }[];
  projectPlanUpdates: {
    id: string;
    title: string;
    ownerRole: string;
    status: string;
    note: string;
    createdAt: string;
  }[];
};

export type RoutingStats = {
  routeAssessmentCount: number;
  rfaReviewCount: number;
  cmReviewCount: number;
  clarificationCount: number;
  analystAssignmentCount: number;
  rfaAcceptanceRate: number;
  cmFallbackRate: number;
};

export type RoutingQueue = {
  tickets: RoutingTicket[];
  stats: RoutingStats;
};

const baseUrl = resolveApiBaseUrl();

export async function listRoutingQueue(route: RoutingRoute): Promise<RoutingQueue> {
  const path = route === "rfa" ? "/api/v1/routing/rfa/queue" : "/api/v1/routing/cm/queue";
  return requestJson<RoutingQueue>(path, { method: "GET" });
}

export async function runRoutingReviews(
  ticketId: string,
  csrfToken: string,
): Promise<RoutingTicket> {
  return requestJson<RoutingTicket>(`/api/v1/routing/${ticketId}/run`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function approveRoute(
  ticketId: string,
  route: RoutingRoute,
  csrfToken: string,
  overrideReason?: string,
): Promise<RoutingTicket> {
  return requestJson<RoutingTicket>(`/api/v1/routing/${ticketId}/approve`, {
    body: JSON.stringify({ route, overrideReason }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function rejectRoute(
  ticketId: string,
  route: RoutingRoute,
  reason: string,
  csrfToken: string,
): Promise<RoutingTicket> {
  return requestJson<RoutingTicket>(`/api/v1/routing/${ticketId}/reject`, {
    body: JSON.stringify({ route, reason }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function requestRouteClarification(
  ticketId: string,
  route: RoutingRoute,
  reason: string,
  questions: string[],
  csrfToken: string,
): Promise<RoutingTicket> {
  return requestJson<RoutingTicket>(`/api/v1/routing/${ticketId}/clarification`, {
    body: JSON.stringify({ route, reason, questions }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

async function requestJson<TResponse>(path: string, init: RequestInit): Promise<TResponse> {
  const response = await fetch(`${baseUrl}${path}`, { ...init, credentials: "include" });
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as TResponse;
}
