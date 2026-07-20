import { apiRequestJson, pathSegment } from "./client";

type FeedbackSubmission = {
  id: string;
  requestId: string;
  rating: number;
  comment: string;
  followUpRequested: boolean;
  createdAt: string;
};

export type FeedbackRequest = {
  id: string;
  ticketId: string;
  ticketReference: string;
  productId: string;
  productTitle: string;
  status: "requested" | "submitted";
  createdAt: string;
  submission: FeedbackSubmission | null;
};

export type FeedbackSubmissionInput = {
  rating: number;
  comment: string;
  followUpRequested: boolean;
};

export type AnalyticsAudience = "admin" | "rfa" | "collection";
export type TeamAnalyticsAudience = Exclude<AnalyticsAudience, "admin">;

export type AdminAnalyticsDashboard = {
  generatedAt: string;
  users: {
    total: number;
    active: number;
    disabled: number;
    passwordResetRequired: number;
    pendingRegistrations: number;
    activeUsers30d: number;
    roleCounts: { role: string; count: number }[];
  };
  assistant: {
    provider: string;
    model: string;
    apiKeyConfigured: boolean;
    chatTurns30d: number;
  };
  search: {
    provider: string;
    model: string;
    apiKeyConfigured: boolean;
    indexStatus: string;
    searchRuns30d: number;
    indexedProducts: number;
    indexedPassages: number;
    indexedRequests: number;
    failedAssets: number;
  };
  voice: {
    model: string;
    enabled: boolean;
    apiKeyConfigured: boolean;
    sessionsStarted30d: number;
    users30d: number;
  };
  audit: {
    windowDays: number;
    retainedEvents: number;
    events30d: number;
    loginSuccesses30d: number;
    loginFailures30d: number;
    securityEvents30d: number;
    configurationChanges30d: number;
    coverageStartsAt: string | null;
    retentionLimitReached: boolean;
  };
  process: {
    remoteRequestsAdmitted: number;
    remoteRequestsDenied: number;
  };
};

export type AnalyticsDashboard = {
  audience: AnalyticsAudience;
  metrics: {
    totalTickets: number;
    activeTickets: number;
    disseminations: number;
    feedbackRequested: number;
    feedbackSubmitted: number;
    averageRating: number | null;
    averageSearchCandidates: number | null;
    rfaRoutes: number;
    collectionRoutes: number;
  };
  productReuse: {
    productId: string;
    reference: string;
    title: string;
    ownerTeam: string;
    disseminationCount: number;
    acceptedOfferCount: number;
    feedbackCount: number;
    averageRating: number | null;
  }[];
  trends: {
    title: string;
    summary: string;
    signal: "positive" | "watch" | "neutral";
    confidence: number;
  }[];
};

export async function listFeedbackRequests(): Promise<FeedbackRequest[]> {
  const response = await apiRequestJson<{ requests: FeedbackRequest[] }>(
    "/api/v1/feedback/requests",
    {
      method: "GET",
    },
  );
  return response.requests;
}

export async function submitFeedback(
  requestId: string,
  payload: FeedbackSubmissionInput,
  csrfToken: string,
): Promise<FeedbackRequest> {
  return apiRequestJson<FeedbackRequest>(
    `/api/v1/feedback/requests/${pathSegment(requestId)}/submit`,
    {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export async function getAnalyticsDashboard(
  audience: TeamAnalyticsAudience,
): Promise<AnalyticsDashboard> {
  return apiRequestJson<AnalyticsDashboard>(`/api/v1/analytics/${audience}`, { method: "GET" });
}

export async function getAdminAnalyticsDashboard(): Promise<AdminAnalyticsDashboard> {
  return apiRequestJson<AdminAnalyticsDashboard>("/api/v1/analytics/admin/platform", {
    method: "GET",
  });
}
