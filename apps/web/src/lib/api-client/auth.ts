import { apiRequestJson, apiRequestNoContent } from "./client";

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
  | "ticket:create"
  | "ticket:read_own"
  | "ticket:read_all"
  | "ticket:write_all"
  | "ticket:add_information"
  | "ticket:add_comment"
  | "ticket:transition"
  | "chat:use"
  | "rfi:search"
  | "rfi:offer_product"
  | "rfi:accept_product"
  | "rfi:reject_product"
  | "jioc:review"
  | "rfa:review"
  | "rfa:assign"
  | "rfa:add_product"
  | "collection:review"
  | "collection:assign"
  | "collection:add_product"
  | "analyst:work"
  | "analyst:submit_product"
  | "product:approve"
  | "team:manage"
  | "qc:review"
  | "qc:approve"
  | "qc:reject"
  | "store:browse_all"
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

export function login(payload: LoginRequest): Promise<AuthSession> {
  return apiRequestJson<AuthSession>("/api/v1/auth/login", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export function getCurrentUser(): Promise<AuthSession> {
  return apiRequestJson<AuthSession>("/api/v1/auth/me", { method: "GET" });
}

export function logout(csrfToken: string): Promise<void> {
  return apiRequestNoContent("/api/v1/auth/logout", {
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export function changePassword(
  payload: ChangePasswordRequest,
  csrfToken: string,
): Promise<AuthSession> {
  return apiRequestJson<AuthSession>("/api/v1/auth/password", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export type AuthApi = {
  login: (payload: LoginRequest) => Promise<AuthSession>;
  getCurrentUser: () => Promise<AuthSession>;
  logout: (csrfToken: string) => Promise<void>;
  changePassword: (payload: ChangePasswordRequest, csrfToken: string) => Promise<AuthSession>;
};

export const defaultAuthApi: AuthApi = { changePassword, getCurrentUser, login, logout };
