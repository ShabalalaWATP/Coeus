import { apiRequestJson, pathSegment } from "./client";
import type { AnalystTask } from "./analyst";
import type { TicketState } from "./tickets";

export type RoutingRoute = "rfa" | "cm";

export type CapabilityTeam = {
  teamId: string;
  name: string;
  department: RoutingRoute;
  keywords: string[];
  workPackages: string[];
  sourceLabels: string[];
  disciplines?: string[];
  regions?: string[];
  rank?: number;
};

type CandidateTeam = {
  teamId: string;
  name: string;
  score: number;
  reasons: string[];
};

export type CapabilityCatalogue = {
  teams: CapabilityTeam[];
};

type CapabilityReview = {
  id: string;
  canSatisfy: boolean;
  confidence: number;
  requiredClarifications: string[];
  estimatedEffort: string;
  risks: string[];
  managerReviewRequired: boolean;
  reasoningSummary: string;
  createdAt: string;
  candidateTeams?: CandidateTeam[];
};

export type RfaCapabilityReview = CapabilityReview & {
  suggestedWorkPackages: string[];
  suggestedTeamId: string | null;
  suggestedTeamName: string | null;
};

export type CmCapabilityReview = CapabilityReview & {
  suggestedCollectionRoute: string | null;
  suggestedCollectionTeamId: string | null;
  suggestedCollectionTeamName: string | null;
  suggestedCollectionSources: string[];
};

type RouteRecommendation = {
  id: string;
  recommendedRoute: "rfa" | "cm" | "clarification";
  reasoningSummary: string;
  createdAt: string;
};

type PriorityAssessment = {
  score: number;
  tier: string;
  reasons: string[];
};

export type RoutingTicket = {
  ticketId: string;
  reference: string;
  requesterUserId: string;
  state: TicketState;
  title: string;
  priority: string | null;
  priorityAssessment?: PriorityAssessment;
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
  agentRuns: string[];
  managerDecisions: {
    id: string;
    route: string;
    status: string;
    reason: string;
    overrideReason: string | null;
    actorUserId: string;
    createdAt: string;
  }[];
  workflowPlanUpdates: {
    id: string;
    title: string;
    ownerRole: string;
    status: string;
    note: string;
    createdAt: string;
  }[];
};

type RoutingStats = {
  jiocQueueCount: number;
  collectChoiceCount: number;
  clarificationCount: number;
  analystAssignmentCount: number;
  rfaAcceptanceRate: number;
  cmFallbackRate: number;
};

export type RoutingQueue = {
  tickets: RoutingTicket[];
  stats: RoutingStats;
  nextCursor?: string | null;
};

export type RoutingQueueKind = RoutingRoute | "jioc";

export async function listRoutingQueue(
  queue: RoutingQueueKind,
  cursor?: string,
): Promise<RoutingQueue> {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return apiRequestJson<RoutingQueue>(`/api/v1/routing/${queue}/queue${query}`, {
    method: "GET",
  });
}

export async function listCapabilityCatalogue(): Promise<CapabilityCatalogue> {
  return apiRequestJson<CapabilityCatalogue>("/api/v1/routing/capability-catalogue", {
    method: "GET",
  });
}

export async function approveManagerWork(
  ticketId: string,
  csrfToken: string,
): Promise<RoutingTicket> {
  return apiRequestJson<RoutingTicket>(
    `/api/v1/routing/${pathSegment(ticketId)}/manager-approval`,
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export async function getManagerWork(ticketId: string): Promise<AnalystTask> {
  return apiRequestJson<AnalystTask>(`/api/v1/routing/${pathSegment(ticketId)}/manager-work`, {
    method: "GET",
  });
}

export async function returnWorkForRework(
  ticketId: string,
  route: RoutingRoute,
  reason: string,
  csrfToken: string,
): Promise<RoutingTicket> {
  return apiRequestJson<RoutingTicket>(`/api/v1/routing/${pathSegment(ticketId)}/manager-rework`, {
    body: JSON.stringify({ route, reason }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function runRoutingReviews(
  ticketId: string,
  csrfToken: string,
): Promise<RoutingTicket> {
  return apiRequestJson<RoutingTicket>(`/api/v1/routing/${pathSegment(ticketId)}/run`, {
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
  return apiRequestJson<RoutingTicket>(`/api/v1/routing/${pathSegment(ticketId)}/approve`, {
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
  return apiRequestJson<RoutingTicket>(`/api/v1/routing/${pathSegment(ticketId)}/reject`, {
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
  return apiRequestJson<RoutingTicket>(`/api/v1/routing/${pathSegment(ticketId)}/clarification`, {
    body: JSON.stringify({ route, reason, questions }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}
