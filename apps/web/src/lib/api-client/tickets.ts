import { apiRequestJson, pathSegment } from "./client";

type IntakeDetails = {
  title: string | null;
  description: string | null;
  operationalQuestion: string | null;
  areaOrRegion: string | null;
  timePeriodStart: string | null;
  timePeriodEnd: string | null;
  priority: string | null;
  deadline: string | null;
  requiredOutputFormat: string | null;
  knownContext: string | null;
  restrictionsOrCaveats: string | null;
  customerSuccessCriteria: string | null;
  suggestedAcgContext: string | null;
  requestingUnit: string | null;
  intelligenceDisciplines: string | null;
  supportedOperation: string | null;
  urgencyJustification: string | null;
  missingInformation: string[];
  confidence: number;
};

type IntakeChecklistItem = {
  key: string;
  label: string;
  value: string | null;
  satisfied: boolean;
};

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

export type Ticket = {
  id: string;
  reference: string;
  requesterUserId: string;
  state: TicketState;
  intake: IntakeDetails;
  intakeChecklist: IntakeChecklistItem[];
  conversationStatus: ConversationStatus;
  collectDisposition: "raw" | "analysed" | null;
  isReadyForSubmission: boolean;
  visibleProductMatches: string[];
  releasedProductIds: string[];
  collaborators: TicketCollaborator[];
  messages: ChatMessage[];
  attachments: AttachmentMetadata[];
  agentRuns: AgentRun[];
  clarificationRequests?: ClarificationRequest[];
  timeline: TimelineEntry[];
  createdAt: string;
  updatedAt: string;
};

export type TicketSummary = {
  id: string;
  reference: string;
  requesterUserId: string;
  state: TicketState;
  title: string | null;
  priority: string | null;
  isReadyForSubmission: boolean;
  collaboratorCount: number;
  releasedProductId: string | null;
  createdAt: string;
  updatedAt: string;
};

export type TicketState =
  | "DRAFT_INTAKE"
  | "INFO_REQUIRED"
  | "RFI_SEARCHING"
  | "RFI_MATCH_OFFERED"
  | "RFI_NO_MATCH"
  | "JIOC_REVIEW"
  | "COLLECT_CHOICE"
  | "ANALYST_ASSIGNMENT"
  | "ANALYST_IN_PROGRESS"
  | "QC_REVIEW"
  | "REWORK_REQUIRED"
  | "MANAGER_APPROVAL"
  | "DISSEMINATION_READY"
  | "CLOSED_DELIVERED"
  | "CLOSED_EXISTING_PRODUCT_ACCEPTED"
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

export async function confirmTicketDelivery(ticketId: string, csrfToken: string): Promise<Ticket> {
  return apiRequestJson<Ticket>(`/api/v1/tickets/${pathSegment(ticketId)}/confirm-delivery`, {
    headers: { "X-CSRF-Token": csrfToken },
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
