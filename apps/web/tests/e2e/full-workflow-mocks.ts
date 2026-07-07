import type { Page, Route } from "@playwright/test";

const API = "http://127.0.0.1:8001/api/v1";
const now = "2026-07-06T12:00:00Z";
const acg = {
  code: "ACG-ALPHA",
  description: "Synthetic",
  id: "acg-alpha",
  isActive: true,
  memberUserIds: ["e2e-user"],
  name: "Alpha",
  ownerUserId: null,
};

export type FlowState = {
  draftSaved: boolean;
  released: boolean;
  stage: "empty" | "draft" | "route" | "review" | "assignment" | "analyst" | "qc" | "release";
  ticketCreated: boolean;
  workPackageDone: boolean;
};
export function createFlowState(): FlowState {
  return {
    draftSaved: false,
    released: false,
    stage: "empty",
    ticketCreated: false,
    workPackageDone: false,
  };
}

export async function installApiMocks(page: Page, flow: FlowState) {
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const method = request.method();

    if (method === "GET" && path === "/auth/me") return json(route, session());
    if (method === "GET" && path === "/notifications") {
      return json(route, { notifications: [], unread: 0 });
    }
    if (method === "GET" && path === "/feedback/requests") return json(route, { requests: [] });
    if (method === "GET" && path === "/users/directory") return json(route, { users: [] });
    if (method === "GET" && path === "/tickets") {
      return json(route, { tickets: flow.ticketCreated ? [ticket(flow)] : [] });
    }
    if (method === "POST" && path === "/chat/messages") {
      flow.ticketCreated = true;
      flow.stage = "draft";
      return json(route, ticket(flow), 201);
    }
    if (method === "POST" && path === "/tickets/ticket-e2e/submit") {
      flow.stage = "route";
      return json(route, ticket(flow, "RFI_SEARCHING"));
    }
    if (method === "GET" && path === "/routing/rfa/queue") {
      return json(route, routingQueue(flow, "queue"));
    }
    if (method === "GET" && path === "/routing/rfa/release-queue") {
      return json(route, routingQueue(flow, "release"));
    }
    if (method === "POST" && path === "/routing/ticket-e2e/run") {
      flow.stage = "review";
      return json(route, routingTicket(flow));
    }
    if (method === "POST" && path === "/routing/ticket-e2e/approve") {
      flow.stage = "assignment";
      return json(route, routingTicket(flow));
    }
    if (method === "GET" && path === "/analyst/candidates") {
      return json(route, {
        analysts: [{ displayName: "Analyst Operator", userId: "analyst-user", username: "a.test" }],
      });
    }
    if (method === "POST" && path === "/analyst/tasks/ticket-e2e/assign") {
      flow.stage = "analyst";
      return json(route, analystTask(flow));
    }
    if (method === "GET" && path === "/analyst/tasks") {
      return json(route, { tasks: flow.stage === "analyst" ? [analystTask(flow)] : [] });
    }
    if (method === "PATCH" && path.includes("/work-packages/package-1")) {
      flow.workPackageDone = true;
      return json(route, analystTask(flow));
    }
    if (method === "POST" && path === "/analyst/tasks/ticket-e2e/drafts") {
      flow.draftSaved = true;
      return json(route, analystTask(flow));
    }
    if (method === "POST" && path === "/analyst/tasks/ticket-e2e/submit-qc") {
      flow.stage = "qc";
      return json(route, analystTask(flow, "QC_REVIEW"));
    }
    if (method === "GET" && path === "/qc/queue")
      return json(route, { products: [qcProduct(flow)] });
    if (method === "GET" && path === "/acgs") return json(route, { acgs: [acg] });
    if (method === "POST" && path === "/qc/products/ticket-e2e/approve") {
      flow.stage = "release";
      return json(route, qcProduct(flow));
    }
    if (method === "POST" && path === "/routing/ticket-e2e/release") {
      flow.released = true;
      return json(route, routingTicket(flow, "DISSEMINATION_READY"));
    }
    return json(route, {});
  });
}

function session() {
  return {
    csrfToken: "csrf-e2e",
    user: {
      defaultRoute: "/app/requests",
      displayName: "Admin Operator",
      id: "e2e-user",
      permissions: ["chat:use", "ticket:read_own", "rfa:review", "analyst:work", "qc:review"],
      roles: ["Administrator"],
      username: "admin@example.test",
    },
  };
}

function ticket(
  flow: FlowState,
  state = flow.stage === "draft" ? "DRAFT_INTAKE" : "RFI_SEARCHING",
) {
  return {
    agentRuns: [],
    attachments: [],
    clarificationRequests: [],
    collaborators: [],
    createdAt: now,
    id: "ticket-e2e",
    intake: intake(),
    isReadyForSubmission: true,
    messages: [{ author: "user", body: "Need a routine assessment.", createdAt: now, id: "m1" }],
    reference: "TCK-E2E",
    releasedProductIds: [],
    requesterUserId: "e2e-user",
    state,
    suggestedProjectName: "North Atlantic Workspace",
    timeline: [],
    updatedAt: now,
    visibleProductMatches: [],
  };
}

function intake() {
  return {
    areaOrRegion: "North Atlantic",
    confidence: 1,
    customerSuccessCriteria: "Support release decision.",
    deadline: "Friday",
    description: "Synthetic request.",
    knownContext: "MOCK DATA ONLY",
    missingInformation: [],
    operationalQuestion: "What activity matters?",
    priority: "routine",
    requiredOutputFormat: "Assessment",
    restrictionsOrCaveats: null,
    suggestedAcgContext: null,
    suggestedProjectName: null,
    timePeriodEnd: null,
    timePeriodStart: null,
    title: "North Atlantic Activity",
  };
}

function routingQueue(flow: FlowState, kind: "queue" | "release") {
  const queueStates = ["route", "review", "assignment"];
  const tickets =
    kind === "release"
      ? flow.stage === "release"
        ? [routingTicket(flow, "MANAGER_RELEASE")]
        : []
      : queueStates.includes(flow.stage)
        ? [routingTicket(flow)]
        : [];
  return {
    stats: {
      analystAssignmentCount: flow.stage === "assignment" ? 1 : 0,
      clarificationCount: 0,
      cmFallbackRate: 0,
      cmReviewCount: 0,
      rfaAcceptanceRate: 1,
      rfaReviewCount: flow.stage === "review" ? 1 : 0,
      routeAssessmentCount: flow.stage === "route" ? 1 : 0,
    },
    tickets,
  };
}

function routingTicket(flow: FlowState, overrideState?: string) {
  const state =
    overrideState ??
    (flow.stage === "assignment"
      ? "ANALYST_ASSIGNMENT"
      : flow.stage === "review"
        ? "RFA_MANAGER_REVIEW"
        : "ROUTE_ASSESSMENT");
  return {
    agentRuns: flow.stage === "route" ? [] : ["rfa-capability-agent", "orchestrator-agent"],
    clarifications: [],
    cmReview: null,
    managerDecisions: [],
    priority: "routine",
    projectPlanUpdates:
      flow.stage === "assignment"
        ? [
            {
              createdAt: now,
              id: "plan-1",
              note: "Approved",
              ownerRole: "Analyst",
              status: "pending",
              title: "Assess vessel activity",
            },
          ]
        : [],
    recommendation:
      flow.stage === "route"
        ? null
        : {
            createdAt: now,
            id: "rec-1",
            reasoningSummary: "RFA can satisfy this request.",
            recommendedRoute: "rfa",
          },
    reference: "TCK-E2E",
    requesterUserId: "e2e-user",
    rfaReview: flow.stage === "route" ? null : capabilityReview(),
    state,
    ticketId: "ticket-e2e",
    title: "North Atlantic Activity",
  };
}

function capabilityReview() {
  return {
    canSatisfy: true,
    confidence: 0.92,
    createdAt: now,
    estimatedEffort: "1 day",
    id: "review-1",
    managerReviewRequired: true,
    reasoningSummary: "RFA can satisfy this request.",
    requiredClarifications: [],
    risks: [],
    suggestedTeamId: "rfa-alpha",
    suggestedTeamName: "Maritime Assessment Cell",
    suggestedWorkPackages: ["Assess vessel activity"],
  };
}

function analystTask(flow: FlowState, state = "ANALYST_IN_PROGRESS") {
  return {
    areaOrRegion: "North Atlantic",
    assignment: {
      analystUserId: "analyst-user",
      assignedByUserId: "e2e-user",
      createdAt: now,
      id: "assignment-1",
      route: "rfa",
      teamName: "Maritime Assessment Cell",
    },
    chatSummary: ["Customer requested assessment."],
    description: "Synthetic request.",
    drafts: flow.draftSaved ? [draft()] : [],
    linkedProducts: [],
    managerNotes: ["RFA route approved."],
    notes: [],
    operationalQuestion: "What activity matters?",
    priority: "routine",
    reference: "TCK-E2E",
    requiredOutputFormat: "Assessment",
    state,
    ticketId: "ticket-e2e",
    title: "North Atlantic Activity",
    workPackages: [
      {
        id: "package-1",
        sortOrder: 1,
        status: flow.workPackageDone ? "complete" : "pending",
        title: "Assess vessel activity",
      },
    ],
  };
}

function draft() {
  return {
    assets: [
      {
        assetType: "pdf",
        id: "asset-1",
        mimeType: "application/pdf",
        name: "assessment-draft.pdf",
        sha256: "e".repeat(64),
        sizeBytes: 512,
      },
    ],
    content: "Synthetic assessment content for QC review.",
    createdAt: now,
    id: "draft-1",
    productType: "finished_output",
    summary: "Synthetic assessment summary.",
    title: "North Atlantic Assessment",
    versionNumber: 1,
  };
}

function qcProduct(flow: FlowState) {
  return {
    areaOrRegion: "North Atlantic",
    checklistKeys: ["source_checked", "classification_checked"],
    decisions: [],
    disseminations: flow.released
      ? [{ id: "dissemination-1", productId: "product-1", recipientUserId: "e2e-user" }]
      : [],
    feedbackRequests: [],
    ingestedProduct:
      flow.stage === "release"
        ? {
            acgIds: ["acg-alpha"],
            id: "product-1",
            reference: "PROD-E2E",
            status: "published",
            title: "North Atlantic Assessment",
          }
        : null,
    indexRecords:
      flow.stage === "release"
        ? [{ id: "index-1", productId: "product-1", status: "indexed", summary: "Indexed." }]
        : [],
    latestDraft: draft(),
    managerNotes: [],
    operationalQuestion: "What activity matters?",
    priority: "routine",
    reference: "TCK-E2E",
    requesterUserId: "e2e-user",
    requiredOutputFormat: "Assessment",
    state: flow.stage === "release" ? "MANAGER_RELEASE" : "QC_REVIEW",
    ticketId: "ticket-e2e",
    title: "North Atlantic Activity",
  };
}

async function json(route: Route, payload: unknown, status = 200) {
  await route.fulfill({ contentType: "application/json", json: payload, status });
}
