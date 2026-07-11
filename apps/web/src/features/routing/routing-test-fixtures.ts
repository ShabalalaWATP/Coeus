import { vi } from "vitest";

import type { RoutingQueue, RoutingTicket } from "../../lib/api-client/routing";

export const baseTicket: RoutingTicket = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "user-1",
  state: "JIOC_REVIEW",
  title: "Arctic Fisheries Assessment",
  priority: "high",
  priorityAssessment: {
    score: 0.77,
    tier: "P2",
    reasons: [
      "priority:level:high",
      "priority:region:tier-1:arctic",
      "priority:unit:carrier-group",
      "priority:operation:standing-task:harbour-sentinel",
    ],
  },
  rfaReview: null,
  cmReview: null,
  recommendation: null,
  clarifications: [],
  agentRuns: [],
  managerDecisions: [],
  workflowPlanUpdates: [],
};

export const reviewedTicket: RoutingTicket = {
  ...baseTicket,
  state: "JIOC_REVIEW",
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
    candidateTeams: [
      {
        teamId: "RFA-MARITIME",
        name: "Maritime Assessment Cell",
        score: 0.79,
        reasons: ["capability:keyword:maritime", "capability:region:arctic", "capability:rank:0.9"],
      },
      {
        teamId: "RFA-GEO",
        name: "Geospatial Assessment Cell",
        score: 0.55,
        reasons: ["capability:keyword:map", "capability:region:global", "capability:rank:0.8"],
      },
    ],
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
  workflowPlanUpdates: [
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
      jiocQueueCount: tickets.filter((ticket) => ticket.state === "JIOC_REVIEW").length,
      collectChoiceCount: tickets.filter((ticket) => ticket.state === "COLLECT_CHOICE").length,
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
      if (url.endsWith("/api/v1/teams")) {
        return Promise.resolve(jsonResponse({ teams: [] }));
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
