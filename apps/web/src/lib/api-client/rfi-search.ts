import { apiRequestJson } from "./client";
import type { TicketState } from "./tickets";

export type RfiProductOffer = {
  productId: string;
  title: string;
  summary: string;
  productType: string;
  matchScore: number;
  matchReasons: string[];
  classificationLevel: number;
  releasability: string[];
  region: string;
  timePeriodStart: string | null;
  timePeriodEnd: string | null;
  assetTypes: string[];
  offerableToUser: boolean;
  status: "offered" | "accepted" | "rejected";
  rejectionReason: string | null;
};

export type RfiSearchMetrics = {
  runId: string;
  query: string;
  candidateCount: number;
  offeredCount: number;
  rejectedCount: number;
  acceptedProductId: string | null;
  createdAt: string;
};

export type RfiSearchResults = {
  ticketId: string;
  ticketState: TicketState;
  offers: RfiProductOffer[];
  metrics: RfiSearchMetrics | null;
};

export async function getRfiSearchResults(ticketId: string): Promise<RfiSearchResults> {
  return apiRequestJson<RfiSearchResults>(`/api/v1/rfi-search/${ticketId}/results`, {
    method: "GET",
  });
}

export async function runRfiSearch(ticketId: string, csrfToken: string): Promise<RfiSearchResults> {
  return apiRequestJson<RfiSearchResults>(`/api/v1/rfi-search/${ticketId}/run`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function acceptProductOffer(
  ticketId: string,
  productId: string,
  csrfToken: string,
): Promise<RfiSearchResults> {
  return apiRequestJson<RfiSearchResults>(
    `/api/v1/rfi-search/${ticketId}/offers/${productId}/accept`,
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export async function rejectProductOffer(
  ticketId: string,
  productId: string,
  reason: string,
  csrfToken: string,
): Promise<RfiSearchResults> {
  return apiRequestJson<RfiSearchResults>(
    `/api/v1/rfi-search/${ticketId}/offers/${productId}/reject`,
    {
      body: JSON.stringify({ reason }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}
