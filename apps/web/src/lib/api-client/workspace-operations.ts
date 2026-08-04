import { apiRequest, apiRequestJson } from "./client";
import type { components } from "./generated/openapi";

type Schemas = components["schemas"];
export type WorkspaceOverview = Schemas["OverviewResponse"];
export type WorkspacePeople = Schemas["PeopleResponse"];
export type WorkspaceCapabilities = Schemas["CapabilitiesResponse"];
export type WorkspacePolicy = Schemas["PolicyResponse"];
export type WorkspaceSearch = Schemas["SearchResponse"];
export type WorkspaceAnalytics = Schemas["AnalyticsResponse"];
export type WorkspaceExport = Schemas["ExportResponse"];
export type WorkspaceSearchResult = Schemas["SearchResultResponse"];
export type WorkspaceScope = "direct" | "descendants";

const path = (unitId: string, operation: string) =>
  `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/${operation}`;

export function getWorkspaceOverview(
  unitId: string,
  scope: WorkspaceScope,
): Promise<WorkspaceOverview> {
  return apiRequestJson(`${path(unitId, "overview")}?scope=${scope}`, { method: "GET" });
}

export function getWorkspacePeople(
  unitId: string,
  scope: WorkspaceScope,
  query = "",
): Promise<WorkspacePeople> {
  const parameters = new URLSearchParams({ scope, limit: "100" });
  if (query.trim().length >= 2) parameters.set("query", query.trim());
  return apiRequestJson(`${path(unitId, "people")}?${parameters}`, { method: "GET" });
}

export function getWorkspaceCapabilities(
  unitId: string,
  scope: WorkspaceScope,
): Promise<WorkspaceCapabilities> {
  return apiRequestJson(`${path(unitId, "capabilities")}?scope=${scope}`, { method: "GET" });
}

export function getWorkspacePolicy(unitId: string): Promise<WorkspacePolicy> {
  return apiRequestJson(path(unitId, "policy"), { method: "GET" });
}

export function saveWorkspacePolicy(
  unitId: string,
  policy: WorkspacePolicy,
  grant: { id: string; version: number },
  csrfToken: string,
): Promise<WorkspacePolicy> {
  return apiRequestJson(path(unitId, "policy"), {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({
      commandId: crypto.randomUUID(),
      idempotencyKey: `workspace-policy-${crypto.randomUUID()}`,
      authorisingGrantId: grant.id,
      expectedGrantVersion: grant.version,
      expectedVersion: policy.version,
      expectedDeliveryPolicyVersion: policy.deliveryPolicyVersion,
      wipLimit: policy.wipLimit,
      serviceTargetHours: policy.serviceTargetHours,
      planningCadence: policy.planningCadence,
      planningWeekday: policy.planningWeekday,
      planningLocalTime: policy.planningLocalTime,
      planningDurationMinutes: policy.planningDurationMinutes,
    }),
  });
}

export function searchWorkspace(
  unitId: string,
  scope: WorkspaceScope,
  query: string,
  storeOnly = false,
): Promise<WorkspaceSearch> {
  const parameters = new URLSearchParams({ scope, query: query.trim(), limit: "20" });
  if (storeOnly) parameters.set("store_only", "true");
  return apiRequestJson(`${path(unitId, "search")}?${parameters}`, { method: "GET" });
}

export function getWorkspaceAnalytics(
  unitId: string,
  scope: WorkspaceScope,
): Promise<WorkspaceAnalytics> {
  return apiRequestJson(`${path(unitId, "analytics")}?scope=${scope}`, { method: "GET" });
}

export function createWorkspaceExport(
  unitId: string,
  includeDescendants: boolean,
  grant: { id: string; version: number },
  csrfToken: string,
): Promise<WorkspaceExport> {
  return apiRequestJson(path(unitId, "exports"), {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({
      commandId: crypto.randomUUID(),
      idempotencyKey: `workspace-export-${crypto.randomUUID()}`,
      exportId: crypto.randomUUID(),
      includeDescendants,
      authorisingGrantId: grant.id,
      expectedGrantVersion: grant.version,
      format: "csv",
    }),
  });
}

export async function downloadWorkspaceExport(exportId: string): Promise<Blob> {
  const response = await apiRequest(
    `/api/v1/organisation/workspaces/exports/${encodeURIComponent(exportId)}/download`,
    { method: "GET" },
  );
  return response.blob();
}
