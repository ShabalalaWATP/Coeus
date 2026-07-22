import { apiRequestJson, pathSegment, resolveApiBaseUrl } from "./client";
import type { TicketState } from "./tickets";
import type { TeamAvailability } from "./teams";

type AnalystAssignment = {
  id: string;
  analystUserId: string;
  assignedByUserId: string;
  route: "rfa" | "cm";
  createdAt: string;
  teamId: string;
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
      detectedMimeType: string;
      previewKind: "pdf" | "image" | "text" | "metadata";
      processingStatus: string;
      previewAvailable: boolean;
    }[];
    description: string;
    sourceType: string;
    ownerTeam: string;
    areaOrRegion: string;
    classificationLevel: number;
    releasability: string[];
    handlingCaveats: string[];
    tags: string[];
    acgIds: string[];
    manifestHash: string;
  }[];
};

export type AnalystTaskList = {
  tasks: AnalystTask[];
};

export type AnalystConversation = {
  messages: {
    id: string;
    author: "user" | "assistant";
    body: string;
    createdAt: string;
  }[];
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

export type ProductSubmissionMetadataInput = {
  title: string;
  summary: string;
  description: string;
  productType: string;
  sourceType: string;
  ownerTeam: string;
  areaOrRegion: string;
  classificationLevel: number;
  releasability: string[];
  handlingCaveats: string[];
  tags: string[];
  acgIds: string[];
  timePeriodStart: string | null;
  timePeriodEnd: string | null;
};

type AnalystCandidate = {
  userId: string;
  username: string;
  displayName: string;
};

export type AnalystCandidateList = {
  analysts: AnalystCandidate[];
};

export type AssignmentTeam = {
  teamId: string;
  name: string;
  kind: "rfa" | "cm";
};

export async function listAnalystTasks(): Promise<AnalystTaskList> {
  return apiRequestJson<AnalystTaskList>("/api/v1/analyst/tasks", { method: "GET" });
}

export async function getAnalystTaskConversation(ticketId: string): Promise<AnalystConversation> {
  return apiRequestJson<AnalystConversation>(
    `/api/v1/analyst/tasks/${pathSegment(ticketId)}/conversation`,
    { method: "GET" },
  );
}

export async function listAnalystCandidates(
  route: "rfa" | "cm",
  teamId: string,
): Promise<AnalystCandidateList> {
  const query = new URLSearchParams({ route, teamId });
  return apiRequestJson<AnalystCandidateList>(`/api/v1/analyst/candidates?${query.toString()}`, {
    method: "GET",
  });
}

export async function listAssignmentTeams(route: "rfa" | "cm"): Promise<AssignmentTeam[]> {
  const response = await apiRequestJson<{ teams: AssignmentTeam[] }>(
    `/api/v1/analyst/assignment-teams?route=${encodeURIComponent(route)}`,
    { method: "GET" },
  );
  return response.teams;
}

export function getAssignmentTeamAvailability(
  route: "rfa" | "cm",
  teamId: string,
  date: string,
): Promise<TeamAvailability> {
  const query = new URLSearchParams({ route, date });
  return apiRequestJson<TeamAvailability>(
    `/api/v1/analyst/assignment-teams/${pathSegment(teamId)}/availability?${query.toString()}`,
    { method: "GET" },
  );
}

export async function assignAnalystTask(
  ticketId: string,
  analystUserIds: string[],
  teamId: string,
  workPackages: string[],
  csrfToken: string,
): Promise<AnalystTask> {
  return apiRequestJson<AnalystTask>(`/api/v1/analyst/tasks/${pathSegment(ticketId)}/assign`, {
    body: JSON.stringify({ analystUserIds, teamId, workPackages }),
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

export async function uploadAnalystProductSubmission(
  ticketId: string,
  metadata: ProductSubmissionMetadataInput,
  asset: File,
  csrfToken: string,
): Promise<AnalystTask> {
  const body = new FormData();
  body.set("metadata", JSON.stringify(metadata));
  body.set("asset", asset, asset.name);
  return apiRequestJson<AnalystTask>(
    `/api/v1/analyst/tasks/${pathSegment(ticketId)}/submissions/upload`,
    {
      body,
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export function workflowProductPreviewUrl(
  ticketId: string,
  versionId: string,
  assetId: string,
): string {
  return `${resolveApiBaseUrl()}/api/v1/workflow/products/${pathSegment(ticketId)}/versions/${pathSegment(versionId)}/assets/${pathSegment(assetId)}/preview`;
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
