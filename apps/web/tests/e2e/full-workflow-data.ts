import { draftProduct } from "./full-workflow-product-data";

const now = "2026-07-06T12:00:00Z";

export const acg = {
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
  qcClaimed: boolean;
  released: boolean;
  stage:
    | "empty"
    | "draft"
    | "route"
    | "review"
    | "assignment"
    | "analyst"
    | "approval"
    | "qc"
    | "release";
  ticketCreated: boolean;
  workPackageDone: boolean;
};

export function createFlowState(): FlowState {
  return {
    draftSaved: false,
    qcClaimed: false,
    released: false,
    stage: "empty",
    ticketCreated: false,
    workPackageDone: false,
  };
}

export function session() {
  return {
    csrfToken: "csrf-e2e",
    user: {
      defaultRoute: "/app/requests",
      displayName: "Admin Operator",
      id: "e2e-user",
      permissions: [
        "chat:use",
        "ticket:read_own",
        "jioc:review",
        "rfa:review",
        "analyst:work",
        "qc:review",
      ],
      roles: ["Administrator"],
      username: "admin@example.test",
    },
  };
}

export function ticket(
  flow: FlowState,
  state = flow.stage === "draft" ? "DRAFT_INTAKE" : "RFI_SEARCHING",
) {
  return {
    agentRuns: [],
    attachments: [],
    clarificationRequests: [],
    collaborators: [],
    collectDisposition: null,
    conversationStatus: "open",
    createdAt: now,
    id: "ticket-e2e",
    intake: intake(),
    intakeChecklist: intakeChecklist(),
    isReadyForSubmission: true,
    messages: [{ author: "user", body: "Need a routine assessment.", createdAt: now, id: "m1" }],
    reference: "TCK-E2E",
    releasedProductIds: [],
    requesterUserId: "e2e-user",
    state,
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
    intelligenceDisciplines: "IMINT",
    knownContext: "MOCK DATA ONLY",
    missingInformation: [],
    operationalQuestion: "What activity matters?",
    priority: "routine",
    requestingUnit: "Carrier Strike Group Atlas",
    requiredOutputFormat: "Assessment",
    restrictionsOrCaveats: null,
    suggestedAcgContext: null,
    supportedOperation: null,
    timePeriodEnd: null,
    timePeriodStart: "next week",
    title: "North Atlantic Activity",
    urgencyJustification: null,
  };
}

function intakeChecklist() {
  const details = intake();
  return [
    { key: "description", label: "What you need", satisfied: true, value: details.description },
    {
      key: "operational_question",
      label: "Question to answer",
      satisfied: true,
      value: details.operationalQuestion,
    },
    {
      key: "area_or_region",
      label: "Area or region",
      satisfied: true,
      value: details.areaOrRegion,
    },
    { key: "time_period", label: "Time period", satisfied: true, value: details.timePeriodStart },
    { key: "priority", label: "Priority", satisfied: true, value: details.priority },
    {
      key: "requesting_unit",
      label: "Requesting unit",
      satisfied: true,
      value: details.requestingUnit,
    },
    {
      key: "intelligence_disciplines",
      label: "Disciplines",
      satisfied: true,
      value: details.intelligenceDisciplines,
    },
    {
      key: "required_output_format",
      label: "Output format",
      satisfied: true,
      value: details.requiredOutputFormat,
    },
    {
      key: "customer_success_criteria",
      label: "Success criteria",
      satisfied: true,
      value: details.customerSuccessCriteria,
    },
    { key: "title", label: "Title", satisfied: true, value: details.title },
  ];
}

export function routingQueue(flow: FlowState, kind: "jioc" | "team") {
  const jiocStates = ["route", "review"];
  const teamStates = ["assignment", "analyst", "approval"];
  const visible = kind === "jioc" ? jiocStates : teamStates;
  const tickets = visible.includes(flow.stage) ? [routingTicket(flow)] : [];
  return {
    stats: {
      analystAssignmentCount: flow.stage === "assignment" ? 1 : 0,
      clarificationCount: 0,
      cmFallbackRate: 0,
      collectChoiceCount: 0,
      jiocQueueCount: flow.stage === "route" || flow.stage === "review" ? 1 : 0,
      rfaAcceptanceRate: 1,
    },
    tickets,
  };
}

export function routingTicket(flow: FlowState, overrideState?: string) {
  const state =
    overrideState ??
    (flow.stage === "approval"
      ? "MANAGER_APPROVAL"
      : flow.stage === "analyst"
        ? "ANALYST_IN_PROGRESS"
        : flow.stage === "assignment"
          ? "ANALYST_ASSIGNMENT"
          : "JIOC_REVIEW");
  return {
    advisoryRuns: [],
    agentRuns: flow.stage === "route" ? [] : ["rfa-capability-agent", "orchestrator-agent"],
    clarifications: [],
    cmReview: flow.stage === "route" ? null : capabilityReview(),
    managerDecisions: [],
    priority: "routine",
    workflowPlanUpdates:
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

export function analystTask(flow: FlowState, state = "ANALYST_IN_PROGRESS") {
  return {
    areaOrRegion: "North Atlantic",
    assignments: [
      {
        analystUserId: "analyst-user",
        assignedByUserId: "e2e-user",
        createdAt: now,
        id: "assignment-1",
        route: "rfa",
        teamName: "Maritime Assessment Cell",
      },
    ],
    chatSummary: ["Customer requested assessment."],
    description: "Synthetic request.",
    drafts: flow.draftSaved ? [draftProduct()] : [],
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
