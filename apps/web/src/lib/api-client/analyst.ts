import { resolveApiBaseUrl, toApiError } from "./client";
import type { TicketState } from "./tickets";

export type AnalystAssignment = {
  id: string;
  analystUserId: string;
  assignedByUserId: string;
  route: "rfa" | "cm";
  createdAt: string;
};

export type WorkPackage = {
  id: string;
  title: string;
  status: "pending" | "complete";
  sortOrder: number;
};

export type AnalystTask = {
  ticketId: string;
  reference: string;
  state: TicketState;
  title: string;
  description: string | null;
  operationalQuestion: string | null;
  areaOrRegion: string | null;
  priority: string | null;
  requiredOutputFormat: string | null;
  chatSummary: string[];
  managerNotes: string[];
  assignment: AnalystAssignment | null;
  workPackages: WorkPackage[];
  notes: { id: string; body: string; createdByUserId: string; createdAt: string }[];
  linkedProducts: {
    id: string;
    productId: string;
    reference: string;
    title: string;
    summary: string;
    createdAt: string;
  }[];
  drafts: {
    id: string;
    versionNumber: number;
    title: string;
    summary: string;
    productType: string;
    content: string;
    createdAt: string;
    assets: {
      id: string;
      name: string;
      assetType: string;
      mimeType: string;
      sizeBytes: number;
      sha256: string;
    }[];
  }[];
};

export type AnalystTaskList = {
  tasks: AnalystTask[];
};

export type DraftProductInput = {
  title: string;
  summary: string;
  productType: string;
  content: string;
  assets: {
    name: string;
    assetType: string;
    mimeType: string;
    sizeBytes: number;
    sha256: string;
  }[];
};

const baseUrl = resolveApiBaseUrl();

export async function listAnalystTasks(): Promise<AnalystTaskList> {
  return requestJson<AnalystTaskList>("/api/v1/analyst/tasks", { method: "GET" });
}

export async function addAnalystNote(
  ticketId: string,
  body: string,
  csrfToken: string,
): Promise<AnalystTask> {
  return requestJson<AnalystTask>(`/api/v1/analyst/tasks/${ticketId}/notes`, {
    body: JSON.stringify({ body }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function linkAnalystProduct(
  ticketId: string,
  productId: string,
  csrfToken: string,
): Promise<AnalystTask> {
  return requestJson<AnalystTask>(`/api/v1/analyst/tasks/${ticketId}/products`, {
    body: JSON.stringify({ productId }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function updateWorkPackage(
  ticketId: string,
  packageId: string,
  status: WorkPackage["status"],
  csrfToken: string,
): Promise<AnalystTask> {
  return requestJson<AnalystTask>(`/api/v1/analyst/tasks/${ticketId}/work-packages/${packageId}`, {
    body: JSON.stringify({ status }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PATCH",
  });
}

export async function saveDraftProduct(
  ticketId: string,
  payload: DraftProductInput,
  csrfToken: string,
): Promise<AnalystTask> {
  return requestJson<AnalystTask>(`/api/v1/analyst/tasks/${ticketId}/drafts`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function submitTaskToQc(ticketId: string, csrfToken: string): Promise<AnalystTask> {
  return requestJson<AnalystTask>(`/api/v1/analyst/tasks/${ticketId}/submit-qc`, {
    headers: { "X-CSRF-Token": csrfToken },
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
