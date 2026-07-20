import { apiRequestJson, pathSegment } from "./client";
import type { components } from "./generated/openapi";

type ApiSchemas = components["schemas"];
type IntakeDetails = ApiSchemas["IntakeDetailsResponse"];

type ConversationStatus = "open" | "close_offered" | "closed";

type ChatMessage = {
  id: string;
  author: "user" | "assistant";
  body: string;
  createdAt: string;
};

type AttachmentMetadata = {
  id: string;
  name: string;
  description: string;
  sourceType: string;
  createdAt: string;
};

type AgentRun = {
  id: string;
  agentName: string;
  status: string;
  summary: string;
  safetyFlags: string[];
  createdAt: string;
};

type TimelineEntry = {
  id: string;
  eventType: string;
  body: string;
  actorUserId: string;
  createdAt: string;
};

type ClarificationRequest = {
  id: string;
  route: string;
  reason: string;
  questions: string[];
  createdAt: string;
};

type TicketCollaborator = {
  userId: string;
  username: string;
  displayName: string;
  access: "editor" | "viewer";
  addedByUserId: string;
  createdAt: string;
};

export type DirectoryUser = {
  id: string;
  username: string;
  displayName: string;
};

export type Ticket = Omit<
  ApiSchemas["TicketResponse"],
  | "state"
  | "conversationStatus"
  | "collectDisposition"
  | "collaborators"
  | "messages"
  | "attachments"
  | "agentRuns"
  | "clarificationRequests"
  | "timeline"
  | "customerStatus"
> & {
  state: TicketState;
  conversationStatus: ConversationStatus;
  collectDisposition: "raw" | "analysed" | null;
  collaborators: TicketCollaborator[];
  messages: ChatMessage[];
  attachments: AttachmentMetadata[];
  agentRuns: AgentRun[];
  clarificationRequests?: ClarificationRequest[];
  timeline: TimelineEntry[];
  customerStatus?: ApiSchemas["CustomerStatusResponse"];
};

export type TicketSummary = Omit<
  ApiSchemas["TicketSummaryResponse"],
  "state" | "customerStatus"
> & {
  state: TicketState;
  customerStatus?: ApiSchemas["CustomerStatusResponse"];
};

export type TicketState =
  | "DRAFT_INTAKE"
  | "INFO_REQUIRED"
  | "RFI_SEARCHING"
  | "RFI_SEARCH_INCOMPLETE"
  | "RFI_MATCH_OFFERED"
  | "ACTIVE_WORK_REVIEW"
  | "ACTIVE_WORK_SEARCH_INCOMPLETE"
  | "RFI_NO_MATCH"
  | "NEW_TASKING_CONSENT"
  | "JIOC_ROUTING_PENDING"
  | "JIOC_INTERVENTION_HOLD"
  | "JIOC_REVIEW"
  | "COLLECT_CHOICE"
  | "ANALYST_ASSIGNMENT"
  | "ANALYST_IN_PROGRESS"
  | "QC_REVIEW"
  | "REWORK_REQUIRED"
  | "MANAGER_APPROVAL"
  | "DISSEMINATION_READY"
  | "MANAGER_REANALYSIS_REVIEW"
  | "JIOC_REANALYSIS_ADJUDICATION"
  | "CLOSED_DELIVERED"
  | "CLOSED_REQUIREMENT_MET"
  | "CLOSED_REANALYSIS_DECLINED"
  | "CLOSED_EXISTING_PRODUCT_ACCEPTED"
  | "CLOSED_UNANSWERED"
  | "CLOSED_JOINED_EXISTING_WORK"
  | "CANCELLED";

export type IntakeUpdate = Partial<
  Pick<
    IntakeDetails,
    | "title"
    | "description"
    | "operationalQuestion"
    | "areaOrRegion"
    | "timePeriodStart"
    | "timePeriodEnd"
    | "priority"
    | "deadline"
    | "requiredOutputFormat"
    | "knownContext"
    | "restrictionsOrCaveats"
    | "customerSuccessCriteria"
    | "suggestedAcgContext"
    | "requestingUnit"
    | "intelligenceDisciplines"
    | "supportedOperation"
    | "urgencyJustification"
  >
>;

export type AttachmentMetadataInput = {
  name: string;
  description: string;
  sourceType: string;
};

export type TicketSummaryPage = {
  tickets: TicketSummary[];
  nextCursor: string | null;
};

export async function listTickets(cursor?: string): Promise<TicketSummaryPage> {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  const response = await apiRequestJson<{ tickets: TicketSummary[]; nextCursor: string | null }>(
    `/api/v1/tickets${query}`,
    {
      method: "GET",
    },
  );
  return response;
}

export async function getTicket(ticketId: string): Promise<Ticket> {
  const response = await apiRequestJson<Ticket | { tickets: Ticket[] }>(
    `/api/v1/tickets/${pathSegment(ticketId)}`,
    {
      method: "GET",
    },
  );
  if ("tickets" in response) {
    const ticket = response.tickets.find((item) => item.id === ticketId);
    if (!ticket) {
      throw new Error("Ticket detail response did not contain the requested ticket.");
    }
    return ticket;
  }
  if (response.id !== ticketId) {
    throw new Error("Ticket detail response did not match the requested ticket.");
  }
  return response;
}

export async function sendChatMessage(
  payload: { ticketId?: string; message: string },
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>("/api/v1/chat/messages", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function reopenTicketConversation(
  ticketId: string,
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/conversation/reopen`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function updateTicketIntake(
  ticketId: string,
  payload: IntakeUpdate,
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/intake`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PATCH",
  });
}

export async function addTicketAttachment(
  ticketId: string,
  payload: AttachmentMetadataInput,
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/attachments`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function submitTicket(ticketId: string, csrfToken: string): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/submit`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function cancelTicket(
  ticketId: string,
  reason: string,
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/cancel`, {
    body: JSON.stringify({ reason }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function consentNoMatch(
  ticketId: string,
  taskAsNewRequest: boolean,
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/no-match-consent`, {
    body: JSON.stringify({ taskAsNewRequest }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function chooseCollectOption(
  ticketId: string,
  analysed: boolean,
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/collect-choice`, {
    body: JSON.stringify({ analysed }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function addTicketInformation(
  ticketId: string,
  body: string,
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/timeline`, {
    body: JSON.stringify({ body }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function listUserDirectory(query: string): Promise<DirectoryUser[]> {
  const params = new URLSearchParams({ q: query });
  const response = await apiRequestJson<{ users: DirectoryUser[] }>(
    `/api/v1/users/directory?${params.toString()}`,
    { method: "GET" },
  );
  return response.users;
}

export async function decideProductOutcome(
  ticketId: string,
  payload: { meetsRequirement: boolean; reason: string; unmetCriteria: string[] },
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/requirement-decision`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function addTicketCollaborator(
  ticketId: string,
  username: string,
  access: "editor" | "viewer",
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/collaborators`, {
    body: JSON.stringify({ username, access }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function removeTicketCollaborator(
  ticketId: string,
  userId: string,
  csrfToken: string,
): Promise<Ticket> {
  return apiRequestJson<Ticket>(
    `/api/v1/tickets/${pathSegment(ticketId)}/collaborators/${pathSegment(userId)}`,
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "DELETE",
    },
  );
}
