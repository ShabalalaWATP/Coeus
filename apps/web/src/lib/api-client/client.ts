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
  | "acg:view"
  | "project:read"
  | "ticket:create"
  | "ticket:read_own"
  | "ticket:read_assigned"
  | "ticket:read_all"
  | "chat:use"
  | "rfi:search"
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
  | "product:read"
  | "product:search"
  | "product:download"
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
};

export type LoginRequest = {
  username: string;
  password: string;
};

type ErrorPayload = {
  error?: {
    code?: string;
    message?: string;
  };
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

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

  private async requestJson<TResponse>(path: string, init: RequestInit): Promise<TResponse> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
    });
    if (!response.ok) {
      throw await toApiError(response);
    }
    return (await response.json()) as TResponse;
  }

  private async requestNoContent(path: string, init: RequestInit): Promise<void> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
    });
    if (!response.ok) {
      throw await toApiError(response);
    }
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  let payload: ErrorPayload = {};
  try {
    payload = (await response.json()) as ErrorPayload;
  } catch {
    payload = {};
  }
  return new ApiError(
    response.status,
    payload.error?.code ?? "request_failed",
    payload.error?.message ?? `API request failed with status ${response.status}`,
  );
}

export function resolveApiBaseUrl(): string {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return configuredUrl ?? "http://127.0.0.1:8001";
}

export const apiClient = new ApiClient(resolveApiBaseUrl());
