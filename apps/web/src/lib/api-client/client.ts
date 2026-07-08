import { toApiError } from "./client-errors";

export { ApiError, setAuthEventHandlers } from "./client-errors";

export type HealthResponse = {
  status: "ok" | "ready" | "not_ready";
  service: string;
  environment: string;
  request_id: string;
};

export type Permission =
  | "auth:login"
  | "auth:logout"
  | "user:read_self"
  | "user:update_self"
  | "user:create"
  | "user:disable"
  | "user:assign_role"
  | "role:manage"
  | "acg:create"
  | "acg:update"
  | "acg:assign_user"
  | "acg:assign_product"
  | "acg:view"
  | "project:create"
  | "project:read"
  | "project:update"
  | "project:add_member"
  | "project:remove_member"
  | "ticket:create"
  | "ticket:read_own"
  | "ticket:read_all"
  | "ticket:add_information"
  | "ticket:add_comment"
  | "ticket:transition"
  | "chat:use"
  | "rfi:search"
  | "rfi:offer_product"
  | "rfi:accept_product"
  | "rfi:reject_product"
  | "rfa:review"
  | "rfa:assign"
  | "rfa:add_product"
  | "collection:review"
  | "collection:assign"
  | "collection:add_product"
  | "analyst:work"
  | "analyst:submit_product"
  | "qc:review"
  | "qc:approve"
  | "qc:reject"
  | "product:create_existing"
  | "product:create_from_qc"
  | "product:read"
  | "product:read_restricted"
  | "product:update_metadata"
  | "product:manage_assets"
  | "product:publish"
  | "product:archive"
  | "product:search"
  | "product:download"
  | "product:disseminate"
  | "feedback:create"
  | "feedback:read"
  | "analytics:view_own"
  | "analytics:view_team"
  | "analytics:view_global"
  | "audit:read"
  | "system:configure";

export type AuthUser = {
  id: string;
  username: string;
  displayName: string;
  roles: readonly string[];
  permissions: readonly Permission[];
  defaultRoute: string;
};

export type AuthSession = {
  user: AuthUser;
  csrfToken: string;
  passwordResetRequired?: boolean;
};

export type LoginRequest = {
  username: string;
  password: string;
};

export type ChangePasswordRequest = {
  currentPassword: string;
  newPassword: string;
};

export type AccessControlGroup = {
  id: string;
  code: string;
  name: string;
  description: string;
  ownerUserId: string | null;
  isActive: boolean;
  memberUserIds: string[];
};

type ProductSummary = {
  id: string;
  title: string;
  summary: string;
  productType: string;
  status: string;
  classificationLevel: number;
  handlingCaveats: string[];
  acgIds: string[];
  ownerTeam: string;
};

type ProjectMember = {
  userId: string;
  role: string;
};

type ProjectMilestone = {
  id: string;
  title: string;
  status: string;
};

type ProjectPlanItem = {
  id: string;
  title: string;
  ownerRole: string;
  status: string;
};

export type ProjectWorkspace = {
  id: string;
  reference: string;
  name: string;
  summary: string;
  requesterUserId: string;
  acgIds: string[];
  ticketIds: string[];
  members: ProjectMember[];
  milestones: ProjectMilestone[];
  planItems: ProjectPlanItem[];
  visibleProducts: ProductSummary[];
};

export type AccessDiagnostics = {
  allowed: boolean;
  reason: string;
  checks: { name: string; passed: boolean; reason: string }[];
};

export type CreateAccessControlGroupRequest = {
  code: string;
  name: string;
  description: string;
  ownerUserId?: string;
};

export type UpdateAccessControlGroupRequest = {
  name?: string;
  description?: string;
  isActive?: boolean;
};

export class ApiClient {
  constructor(private readonly baseUrl: string) {}

  async getJson<TResponse>(path: string, requestId?: string): Promise<TResponse> {
    return this.requestJson<TResponse>(path, {
      headers: requestId === undefined ? undefined : { "X-Request-ID": requestId },
      method: "GET",
    });
  }

  async getLiveness(requestId?: string): Promise<HealthResponse> {
    return this.getJson<HealthResponse>("/api/v1/health/live", requestId);
  }

  async login(payload: LoginRequest): Promise<AuthSession> {
    return this.requestJson<AuthSession>("/api/v1/auth/login", {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
  }

  async getCurrentUser(): Promise<AuthSession> {
    return this.requestJson<AuthSession>("/api/v1/auth/me", { method: "GET" });
  }

  async logout(csrfToken: string): Promise<void> {
    await this.requestNoContent("/api/v1/auth/logout", {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    });
  }

  async changePassword(payload: ChangePasswordRequest, csrfToken: string): Promise<AuthSession> {
    return this.requestJson<AuthSession>("/api/v1/auth/password", {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    });
  }

  async listAcgs(): Promise<AccessControlGroup[]> {
    const response = await this.requestJson<{ acgs: AccessControlGroup[] }>("/api/v1/acgs", {
      method: "GET",
    });
    return response.acgs;
  }

  async createAcg(
    payload: CreateAccessControlGroupRequest,
    csrfToken: string,
  ): Promise<AccessControlGroup> {
    return this.requestJson<AccessControlGroup>("/api/v1/acgs", {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    });
  }

  async updateAcg(
    acgId: string,
    payload: UpdateAccessControlGroupRequest,
    csrfToken: string,
  ): Promise<AccessControlGroup> {
    return this.requestJson<AccessControlGroup>(`/api/v1/acgs/${pathSegment(acgId)}`, {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "PATCH",
    });
  }

  async addAcgMember(
    acgId: string,
    userId: string,
    csrfToken: string,
  ): Promise<AccessControlGroup> {
    return this.requestJson<AccessControlGroup>(`/api/v1/acgs/${pathSegment(acgId)}/members`, {
      body: JSON.stringify({ userId }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    });
  }

  async listProjects(): Promise<ProjectWorkspace[]> {
    const response = await this.requestJson<{ projects: ProjectWorkspace[] }>("/api/v1/projects", {
      method: "GET",
    });
    return response.projects;
  }

  async getProject(projectId: string): Promise<ProjectWorkspace> {
    return this.requestJson<ProjectWorkspace>(`/api/v1/projects/${pathSegment(projectId)}`, {
      method: "GET",
    });
  }

  async diagnoseProductAccess(
    productId: string,
    userId: string,
    csrfToken: string,
  ): Promise<AccessDiagnostics> {
    return this.requestJson<AccessDiagnostics>(
      `/api/v1/store/products/${pathSegment(productId)}/access-diagnostics`,
      {
        body: JSON.stringify({ userId }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        method: "POST",
      },
    );
  }

  private async requestJson<TResponse>(path: string, init: RequestInit): Promise<TResponse> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
    });
    if (!response.ok) {
      throw await toApiError(response, path);
    }
    return (await response.json()) as TResponse;
  }

  private async requestNoContent(path: string, init: RequestInit): Promise<void> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
    });
    if (!response.ok) {
      throw await toApiError(response, path);
    }
  }
}

export async function apiRequestJson<TResponse>(
  path: string,
  init: RequestInit,
): Promise<TResponse> {
  const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
    ...init,
    credentials: "include",
  });
  if (!response.ok) {
    throw await toApiError(response, path);
  }
  return (await response.json()) as TResponse;
}

export function resolveApiBaseUrl(): string {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return configuredUrl ?? "http://127.0.0.1:8001";
}

export function pathSegment(value: string): string {
  return encodeURIComponent(value);
}

export const apiClient = new ApiClient(resolveApiBaseUrl());
