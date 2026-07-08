import { vi } from "vitest";

import type { RoutingQueue, RoutingTicket } from "../../lib/api-client/routing";

export const baseTicket: RoutingTicket = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "user-1",
  state: "ROUTE_ASSESSMENT",
  title: "Arctic Fisheries Assessment",
  priority: "high",
  rfaReview: null,
  cmReview: null,
  recommendation: null,
  clarifications: [],
  agentRuns: [],
  managerDecisions: [],
  projectPlanUpdates: [],
};

export const reviewedTicket: RoutingTicket = {
  ...baseTicket,
  state: "RFA_MANAGER_REVIEW",
  recommendation: {
    id: "recommendation-1",
    recommendedRoute: "rfa",
    reasoningSummary: "RFA route preferred because assessment can satisfy the request.",
    createdAt: "2026-07-05T00:00:00Z",
  },
  rfaReview: {
    id: "rfa-review-1",
    canSatisfy: true,
    confidence: 0.86,
    requiredClarifications: [],
    suggestedWorkPackages: ["Validate assumptions."],
    suggestedTeamId: "RFA-MARITIME",
    suggestedTeamName: "Maritime Assessment Cell",
    estimatedEffort: "1-2 days",
    risks: [],
    managerReviewRequired: true,
    reasoningSummary: "RFA can satisfy the request with assessment-led work packages.",
    createdAt: "2026-07-05T00:00:00Z",
  },
  cmReview: {
    id: "cm-review-1",
    canSatisfy: false,
    confidence: 0.34,
    requiredClarifications: [],
    suggestedCollectionRoute: null,
    suggestedCollectionTeamId: null,
    suggestedCollectionTeamName: null,
    suggestedCollectionSources: [],
    estimatedEffort: "1-2 days",
    risks: [],
    managerReviewRequired: true,
    reasoningSummary: "No strong collection signal was found in the intake.",
    createdAt: "2026-07-05T00:00:00Z",
  },
  projectPlanUpdates: [
    {
      id: "plan-1",
      title: "RFA manager route review",
      ownerRole: "RFA Manager",
      status: "proposed",
      note: "RFA route preferred.",
      createdAt: "2026-07-05T00:00:00Z",
    },
  ],
};

const capabilityCatalogue = {
  teams: [
    {
      teamId: "RFA-MARITIME",
      name: "Maritime Assessment Cell",
      department: "rfa",
      keywords: ["maritime", "port", "vessel"],
      workPackages: ["Validate the requirement with Maritime Assessment Cell."],
      sourceLabels: [],
    },
    {
      teamId: "CM-CYBER-SENSOR",
      name: "Cyber Sensor Coordination Cell",
      department: "cm",
      keywords: ["sensor", "telemetry", "cyber"],
      workPackages: ["Confirm collection feasibility with Cyber Sensor Coordination Cell."],
      sourceLabels: ["cyber sensor coordination", "collection manager coordination"],
    },
  ],
};

export function queueWith(tickets: RoutingTicket[]): RoutingQueue {
  return {
    tickets,
    stats: {
      routeAssessmentCount: 1,
      rfaReviewCount: tickets.filter((ticket) => ticket.state === "RFA_MANAGER_REVIEW").length,
      cmReviewCount: tickets.filter((ticket) => ticket.state === "CM_MANAGER_REVIEW").length,
      clarificationCount: 0,
      analystAssignmentCount: 0,
      rfaAcceptanceRate: 0,
      cmFallbackRate: 0,
    },
  };
}

export function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}

type MockResponse = ReturnType<typeof jsonResponse>;

export function stubRoutingFetch(
  sequential: ReturnType<typeof vi.fn<(url: string, init?: RequestInit) => Promise<MockResponse>>>,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.includes("release-queue")) {
        return Promise.resolve(jsonResponse(queueWith([])));
      }
      if (url.includes("capability-catalogue")) {
        return Promise.resolve(jsonResponse(capabilityCatalogue));
      }
      if (url.includes("similar-requests/routing") && !url.includes("/link/")) {
        return Promise.resolve(jsonResponse({ matches: [] }));
      }
      return sequential(url, init);
    }),
  );
  return sequential;
}
