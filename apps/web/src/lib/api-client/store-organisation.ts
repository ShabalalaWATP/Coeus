import { apiRequest, apiRequestJson, pathSegment } from "./client";
import type { components } from "./generated/openapi";

export type StoreProject = components["schemas"]["ProjectDetailResponse"];
export type StoreProjectSummary = components["schemas"]["ProjectSummaryResponse"];
export type StoreProjectCreateInput = components["schemas"]["ProjectCreateRequest"];
export type StoreSubscription = components["schemas"]["SubscriptionResponse"];
export type StoreSubscriptionInput = components["schemas"]["SubscriptionUpsertRequest"];

export function getStoreProjects(): Promise<StoreProjectSummary[]> {
  return apiRequestJson<StoreProjectSummary[]>("/api/v1/store/projects", { method: "GET" });
}

export function getStoreProject(projectId: string): Promise<StoreProject> {
  return apiRequestJson<StoreProject>(`/api/v1/store/projects/${pathSegment(projectId)}`, {
    method: "GET",
  });
}

export function createStoreProject(
  payload: StoreProjectCreateInput,
  csrfToken: string,
): Promise<StoreProject> {
  return projectMutation("/api/v1/store/projects", "POST", csrfToken, payload);
}

export function addStoreProjectMember(
  projectId: string,
  username: string,
  csrfToken: string,
): Promise<StoreProject> {
  return projectMutation(
    `/api/v1/store/projects/${pathSegment(projectId)}/members`,
    "POST",
    csrfToken,
    { username },
  );
}

export function removeStoreProjectMember(
  projectId: string,
  memberId: string,
  csrfToken: string,
): Promise<StoreProject> {
  return projectMutation(
    `/api/v1/store/projects/${pathSegment(projectId)}/members/${pathSegment(memberId)}`,
    "DELETE",
    csrfToken,
  );
}

export function setStoreProjectArchived(
  projectId: string,
  archived: boolean,
  csrfToken: string,
): Promise<StoreProject> {
  return projectMutation(
    `/api/v1/store/projects/${pathSegment(projectId)}/status`,
    "PUT",
    csrfToken,
    { archived },
  );
}

export function addStoreProjectProduct(
  projectId: string,
  productId: string,
  csrfToken: string,
): Promise<StoreProject> {
  return projectMutation(
    `/api/v1/store/projects/${pathSegment(projectId)}/products/${pathSegment(productId)}`,
    "PUT",
    csrfToken,
  );
}

export function removeStoreProjectProduct(
  projectId: string,
  productId: string,
  csrfToken: string,
): Promise<StoreProject> {
  return projectMutation(
    `/api/v1/store/projects/${pathSegment(projectId)}/products/${pathSegment(productId)}`,
    "DELETE",
    csrfToken,
  );
}

export function addStoreProjectEntry(
  projectId: string,
  kind: "note" | "question",
  body: string,
  csrfToken: string,
): Promise<StoreProject> {
  return projectMutation(
    `/api/v1/store/projects/${pathSegment(projectId)}/entries`,
    "POST",
    csrfToken,
    { kind, body },
  );
}

export function getStoreSubscriptions(): Promise<StoreSubscription[]> {
  return apiRequestJson<StoreSubscription[]>("/api/v1/store/subscriptions", { method: "GET" });
}

export function createStoreSubscription(
  payload: StoreSubscriptionInput,
  csrfToken: string,
): Promise<StoreSubscription> {
  return subscriptionMutation("/api/v1/store/subscriptions", "POST", payload, csrfToken);
}

export function updateStoreSubscription(
  subscriptionId: string,
  payload: StoreSubscriptionInput,
  csrfToken: string,
): Promise<StoreSubscription> {
  return subscriptionMutation(
    `/api/v1/store/subscriptions/${pathSegment(subscriptionId)}`,
    "PUT",
    payload,
    csrfToken,
  );
}

export async function deleteStoreSubscription(
  subscriptionId: string,
  csrfToken: string,
): Promise<void> {
  await apiRequest(`/api/v1/store/subscriptions/${pathSegment(subscriptionId)}`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "DELETE",
  });
}

function projectMutation(
  path: string,
  method: "DELETE" | "POST" | "PUT",
  csrfToken: string,
  body?: object,
): Promise<StoreProject> {
  return apiRequestJson<StoreProject>(path, {
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      "X-CSRF-Token": csrfToken,
    },
    method,
  });
}

function subscriptionMutation(
  path: string,
  method: "POST" | "PUT",
  body: StoreSubscriptionInput,
  csrfToken: string,
): Promise<StoreSubscription> {
  return apiRequestJson<StoreSubscription>(path, {
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method,
  });
}
