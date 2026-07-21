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

export type CapabilityCatalogue = { teams: CapabilityTeam[] };

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

type JiocAgentDecision = {
  id: string;
  recommendedRoute: "rfa" | "cm" | "clarification";
  disposition: "auto_applied" | "clarification" | "manager_review";
  confidence: number;
  rationaleCodes: string[];
  policyVersion: string;
  createdAt: string;
};

type PriorityAssessment = { score: number; tier: string; reasons: string[] };

export type AdvisoryAgentKind = "intake_planner" | "search_planner" | "routing_critic";

export type AdvisoryAgentRun = {
  id: string;
  agentName: string;
  status: string;
  summary: string;
  safetyFlags: string[];
  createdAt: string;
  advice: {
    agent: AdvisoryAgentKind;
    outcome: string;
    verdict: string | null;
    shadowOnly: boolean;
    contextReferences: string[];
    items: {
      kind: string;
      code: string;
      detail: string;
      references: string[];
    }[];
    providerAttempted: boolean;
  };
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
  jiocAgentDecision?: JiocAgentDecision | null;
  clarifications: {
    id: string;
    route: string;
    reason: string;
    questions: string[];
    requestedByUserId: string;
    createdAt: string;
  }[];
  agentRuns: string[];
  advisoryRuns: AdvisoryAgentRun[];
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
  reanalysisContext?: {
    productId: string;
    customerReason: string;
    unmetCriteria: string[];
    managerRationale: string | null;
  } | null;
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

type OversightCount = { key: string; count: number };
export type JiocOversight = {
  countsByState: OversightCount[];
  countsByRoute: OversightCount[];
  teams: {
    teamId: string;
    name: string;
    kind: string;
    activeMembers: number;
    availableMembers: number;
    liveTaskCount: number;
  }[];
  analysts: {
    userId: string;
    displayName: string;
    teamIds: string[];
    liveTaskCount: number;
  }[];
  tasks: {
    ticketId: string;
    reference: string;
    state: TicketState;
    route: string | null;
    teamId: string | null;
    teamName: string | null;
    analystCount: number;
    workPackageCount: number;
    completedWorkPackageCount: number;
    agentDisposition?: string | null;
    agentConfidence?: number | null;
    criticVerdict: string | null;
    criticOutcome: string | null;
    criticChallengeCount: number;
    criticMissingEvidenceCount: number;
  }[];
};
