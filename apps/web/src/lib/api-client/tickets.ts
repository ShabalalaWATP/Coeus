import { resolveApiBaseUrl, toApiError } from "./client";

export type IntakeDetails = {
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
  suggestedProjectName: string | null;
  suggestedAcgContext: string | null;
  missingInformation: string[];
  confidence: number;
};

export type ChatMessage = {
  id: string;
  author: "user" | "assistant";
  body: string;
  createdAt: string;
};

export type AttachmentMetadata = {
  id: string;
  name: string;
  description: string;
  sourceType: string;
  createdAt: string;
};

export type AgentRun = {
  id: string;
  agentName: string;
  status: string;
  summary: string;
  safetyFlags: string[];
  createdAt: string;
};

export type TimelineEntry = {
  id: string;
  eventType: string;
  body: string;
  actorUserId: string;
  createdAt: string;
};

export type Ticket = {
  id: string;
  reference: string;
  requesterUserId: string;
  state: TicketState;
  intake: IntakeDetails;
  isReadyForSubmission: boolean;
  suggestedProjectName: string | null;
  visibleProductMatches: string[];
  messages: ChatMessage[];
  attachments: AttachmentMetadata[];
  agentRuns: AgentRun[];
  timeline: TimelineEntry[];
  createdAt: string;
  updatedAt: string;
};

export type TicketState =
  | "DRAFT_INTAKE"
  | "INFO_REQUIRED"
  | "RFI_SEARCHING"
  | "RFI_MATCH_OFFERED"
  | "ROUTE_ASSESSMENT"
  | "RFA_MANAGER_REVIEW"
  | "CM_MANAGER_REVIEW"
  | "ANALYST_ASSIGNMENT"
  | "ANALYST_IN_PROGRESS"
  | "QC_REVIEW"
  | "REWORK_REQUIRED"
  | "DISSEMINATION_READY"
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
  >
>;

export type AttachmentMetadataInput = {
  name: string;
  description: string;
  sourceType: string;
};

const baseUrl = resolveApiBaseUrl();

export async function listTickets(): Promise<Ticket[]> {
  const response = await requestJson<{ tickets: Ticket[] }>("/api/v1/tickets", { method: "GET" });
  return response.tickets;
}

export async function sendChatMessage(
  payload: { ticketId?: string; message: string },
  csrfToken: string,
): Promise<Ticket> {
  return requestJson<Ticket>("/api/v1/chat/messages", {
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
  return requestJson<Ticket>(`/api/v1/tickets/${ticketId}/intake`, {
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
  return requestJson<Ticket>(`/api/v1/tickets/${ticketId}/attachments`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function submitTicket(ticketId: string, csrfToken: string): Promise<Ticket> {
  return requestJson<Ticket>(`/api/v1/tickets/${ticketId}/submit`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function addTicketInformation(
  ticketId: string,
  body: string,
  csrfToken: string,
): Promise<Ticket> {
  return requestJson<Ticket>(`/api/v1/tickets/${ticketId}/timeline`, {
    body: JSON.stringify({ body }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

async function requestJson<TResponse>(path: string, init: RequestInit): Promise<TResponse> {
  const response = await fetch(`${baseUrl}${path}`, { ...init, credentials: "include" });
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as TResponse;
}
