import { apiRequestJson, pathSegment } from "./client";
import type { TicketState } from "./tickets";

type AnalystAssignment = {
  id: string;
  analystUserId: string;
  assignedByUserId: string;
  route: "rfa" | "cm";
  createdAt: string;
  teamName: string | null;
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
  assignments: AnalystAssignment[];
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

type AnalystCandidate = {
  userId: string;
  username: string;
  displayName: string;
};

export type AnalystCandidateList = {
  analysts: AnalystCandidate[];
};

export async function listAnalystTasks(): Promise<AnalystTaskList> {
  return apiRequestJson<AnalystTaskList>("/api/v1/analyst/tasks", { method: "GET" });
}

export async function listAnalystCandidates(route: "rfa" | "cm"): Promise<AnalystCandidateList> {
  return apiRequestJson<AnalystCandidateList>(
    `/api/v1/analyst/candidates?route=${encodeURIComponent(route)}`,
    { method: "GET" },
  );
}

export async function assignAnalystTask(
  ticketId: string,
  analystUserIds: string[],
  teamName: string,
  workPackages: string[],
  csrfToken: string,
): Promise<AnalystTask> {
  return apiRequestJson<AnalystTask>(`/api/v1/analyst/tasks/${pathSegment(ticketId)}/assign`, {
    body: JSON.stringify({ analystUserIds, teamName: teamName || undefined, workPackages }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function addAnalystNote(
  ticketId: string,
  body: string,
  csrfToken: string,
): Promise<AnalystTask> {
  return apiRequestJson<AnalystTask>(`/api/v1/analyst/tasks/${pathSegment(ticketId)}/notes`, {
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
  return apiRequestJson<AnalystTask>(`/api/v1/analyst/tasks/${pathSegment(ticketId)}/products`, {
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
  return apiRequestJson<AnalystTask>(
    `/api/v1/analyst/tasks/${pathSegment(ticketId)}/work-packages/${pathSegment(packageId)}`,
    {
      body: JSON.stringify({ status }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "PATCH",
    },
  );
}

export async function saveDraftProduct(
  ticketId: string,
  payload: DraftProductInput,
  csrfToken: string,
): Promise<AnalystTask> {
  return apiRequestJson<AnalystTask>(`/api/v1/analyst/tasks/${pathSegment(ticketId)}/drafts`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function submitTaskForReview(
  ticketId: string,
  csrfToken: string,
): Promise<AnalystTask> {
  return apiRequestJson<AnalystTask>(`/api/v1/analyst/tasks/${pathSegment(ticketId)}/submit`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}
