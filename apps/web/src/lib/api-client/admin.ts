import { apiRequestJson, pathSegment } from "./client";

export type AiModelState = {
  provider: string;
  activeModel: string;
  availableModels: string[];
  apiKeyConfigured: boolean;
  embeddingProvider: string;
  embeddedProductCount: number;
  changedBy: string | null;
  changedAt: string | null;
};

export type AdminUser = {
  id: string;
  username: string;
  displayName: string;
  roles: string[];
  clearanceLevel: number;
  isActive: boolean;
};

export type CredentialReset = {
  temporaryCredential: string;
};

export type AdminOverview = {
  status: string;
  scope: string;
  userId: string;
};

export function getAdminOverview(): Promise<AdminOverview> {
  return apiRequestJson<AdminOverview>("/api/v1/admin/overview", { method: "GET" });
}

export async function getAiModelState(): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model", { method: "GET" });
}

export async function selectAiModel(model: string, csrfToken: string): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model", {
    body: JSON.stringify({ model }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export async function configureAiApiKey(apiKey: string, csrfToken: string): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model/api-key", {
    body: JSON.stringify({ apiKey }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  const response = await apiRequestJson<{ users: AdminUser[] }>("/api/v1/admin/users", {
    method: "GET",
  });
  return response.users;
}

export async function updateAdminUserRoles(
  userId: string,
  roles: string[],
  csrfToken: string,
): Promise<AdminUser> {
  return apiRequestJson<AdminUser>(`/api/v1/admin/users/${pathSegment(userId)}/roles`, {
    body: JSON.stringify({ roles }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export async function updateAdminUserClearance(
  userId: string,
  clearanceLevel: number,
  csrfToken: string,
): Promise<AdminUser> {
  return apiRequestJson<AdminUser>(`/api/v1/admin/users/${pathSegment(userId)}/clearance`, {
    body: JSON.stringify({ clearanceLevel }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export async function updateAdminUserStatus(
  userId: string,
  isActive: boolean,
  csrfToken: string,
): Promise<AdminUser> {
  return apiRequestJson<AdminUser>(`/api/v1/admin/users/${pathSegment(userId)}/status`, {
    body: JSON.stringify({ isActive }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export async function resetAdminUserCredential(
  userId: string,
  csrfToken: string,
): Promise<CredentialReset> {
  return apiRequestJson<CredentialReset>(
    `/api/v1/admin/users/${pathSegment(userId)}/credential-reset`,
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}
