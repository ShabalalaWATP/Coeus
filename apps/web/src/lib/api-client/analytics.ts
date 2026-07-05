import { apiRequestJson } from "./client";

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
  return apiRequestJson<FeedbackRequest>(`/api/v1/feedback/requests/${requestId}/submit`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function getAnalyticsDashboard(
  audience: AnalyticsAudience,
): Promise<AnalyticsDashboard> {
  return apiRequestJson<AnalyticsDashboard>(`/api/v1/analytics/${audience}`, { method: "GET" });
}
