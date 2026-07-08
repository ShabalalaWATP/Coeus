import { apiRequestJson, pathSegment } from "./client";

type SimilarRequestMatch = {
  ticketId: string;
  reference: string;
  title: string;
  state: string;
  score: number;
  reasons: string[];
  alreadyLinked: boolean;
};

export type SimilarRequestNotice = {
  matches: SimilarRequestMatch[];
};

export type SimilarRequestList = {
  matches: SimilarRequestMatch[];
};

export type SimilarRequestJoin = {
  joinedTicketId: string;
  reference: string;
};

export async function getSimilarRequestNotice(ticketId: string): Promise<SimilarRequestNotice> {
  return apiRequestJson<SimilarRequestNotice>(
    `/api/v1/similar-requests/tickets/${pathSegment(ticketId)}`,
    { method: "GET" },
  );
}

export async function joinSimilarRequest(
  ticketId: string,
  relatedTicketId: string,
  csrfToken: string,
): Promise<SimilarRequestJoin> {
  return apiRequestJson<SimilarRequestJoin>(
    `/api/v1/similar-requests/tickets/${pathSegment(ticketId)}/join/${pathSegment(relatedTicketId)}`,
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export async function listRoutingSimilarRequests(ticketId: string): Promise<SimilarRequestList> {
  return apiRequestJson<SimilarRequestList>(
    `/api/v1/similar-requests/routing/${pathSegment(ticketId)}`,
    { method: "GET" },
  );
}

export async function linkRoutingSimilarRequest(
  ticketId: string,
  relatedTicketId: string,
  csrfToken: string,
): Promise<SimilarRequestList> {
  return apiRequestJson<SimilarRequestList>(
    `/api/v1/similar-requests/routing/${pathSegment(ticketId)}/link/${pathSegment(relatedTicketId)}`,
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}
