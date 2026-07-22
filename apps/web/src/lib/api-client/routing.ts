import { apiRequestJson, pathSegment } from "./client";
import type { AnalystTask } from "./analyst";
import type {
  CapabilityCatalogue,
  JiocOversight,
  RoutingQueue,
  RoutingQueueKind,
  RoutingRoute,
  RoutingTicket,
} from "./routing-types";

export type {
  AdvisoryAgentKind,
  AdvisoryAgentRun,
  CapabilityCatalogue,
  CapabilityTeam,
  CmCapabilityReview,
  JiocOversight,
  RfaCapabilityReview,
  RoutingQueue,
  RoutingQueueKind,
  RoutingRoute,
  RoutingTicket,
} from "./routing-types";

export async function listRoutingQueue(
  queue: RoutingQueueKind,
  cursor?: string,
): Promise<RoutingQueue> {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return apiRequestJson<RoutingQueue>(`/api/v1/routing/${queue}/queue${query}`, {
    method: "GET",
  });
}

export async function getJiocOversight(): Promise<JiocOversight> {
  return apiRequestJson<JiocOversight>("/api/v1/routing/oversight", { method: "GET" });
}

export async function interveneInRouting(
  ticketId: string,
  action: "hold" | "resume" | "send_to_review",
  reason: string,
  csrfToken: string,
): Promise<RoutingTicket> {
  return apiRequestJson<RoutingTicket>(`/api/v1/routing/${pathSegment(ticketId)}/intervene`, {
    body: JSON.stringify({ action, reason }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
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

export async function decideManagerReanalysis(
  ticketId: string,
  decision: "agree" | "refer_to_jioc",
  rationale: string,
  csrfToken: string,
): Promise<RoutingTicket> {
  return apiRequestJson<RoutingTicket>(
    `/api/v1/routing/${pathSegment(ticketId)}/reanalysis-manager-decision`,
    {
      body: JSON.stringify({ decision, rationale }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export async function decideJiocReanalysis(
  ticketId: string,
  decision: "reanalyse" | "close",
  rationale: string,
  csrfToken: string,
): Promise<RoutingTicket> {
  return apiRequestJson<RoutingTicket>(
    `/api/v1/routing/${pathSegment(ticketId)}/jioc-reanalysis-decision`,
    {
      body: JSON.stringify({ decision, rationale }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}
