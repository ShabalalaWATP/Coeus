import { apiRequestJson, pathSegment } from "./client";

type SimilarRequestMatch = {
  ticketId: string;
  reference: string;
  title: string;
  state: string;
  score: number;
  reasons: string[];
  alreadyLinked: boolean;
  alreadyMarkedDuplicate: boolean;
  requestKind: string;
  approvedRoute: string | null;
  assignedTeam: string | null;
  requestingUnit: string | null;
  supportedOperation: string | null;
  timePeriodStart: string | null;
  timePeriodEnd: string | null;
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

export async function markRoutingDuplicate(
  ticketId: string,
  relatedTicketId: string,
  withdrawSource: boolean,
  csrfToken: string,
): Promise<SimilarRequestList> {
  return apiRequestJson<SimilarRequestList>(
    `/api/v1/similar-requests/routing/${pathSegment(ticketId)}/duplicate/${pathSegment(relatedTicketId)}`,
    {
      body: JSON.stringify({ withdrawSource }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}
