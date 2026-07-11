import { apiRequestJson, pathSegment } from "./client";

export type AiProviderState = {
  name: string;
  label: string;
  models: string[];
  activeModel: string;
  apiKeyConfigured: boolean;
};

export type AiModelState = {
  provider: string;
  activeModel: string;
  availableModels: string[];
  apiKeyConfigured: boolean;
  embeddingProvider: string;
  embeddedProductCount: number;
  changedBy: string | null;
  changedAt: string | null;
  providers: AiProviderState[];
};

export type AiConnectionTest = {
  ok: boolean;
  provider: string;
  model: string;
  message: string;
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

export async function selectAiModel(
  model: string,
  provider: string,
  csrfToken: string,
): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model", {
    body: JSON.stringify({ model, provider }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export async function selectAiProvider(provider: string, csrfToken: string): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model/provider", {
    body: JSON.stringify({ provider }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export async function testAiConnection(
  provider: string,
  csrfToken: string,
): Promise<AiConnectionTest> {
  return apiRequestJson<AiConnectionTest>("/api/v1/admin/ai-model/test", {
    body: JSON.stringify({ provider }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function refreshAiModels(provider: string, csrfToken: string): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model/refresh", {
    body: JSON.stringify({ provider }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function addCustomAiModel(
  provider: string,
  model: string,
  csrfToken: string,
): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model/custom-model", {
    body: JSON.stringify({ provider, model }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function configureAiApiKey(
  apiKey: string,
  provider: string,
  csrfToken: string,
): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model/api-key", {
    body: JSON.stringify({ apiKey, provider }),
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
