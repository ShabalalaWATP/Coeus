import { apiRequestJson, apiRequestNoContent, pathSegment } from "./client";

type AccessGroupApplicationStatus = "pending" | "approved" | "rejected" | "withdrawn" | null;

export type AccessGroupSummary = {
  id: string;
  code: string;
  name: string;
  description: string;
  isMember: boolean;
  applicationStatus: AccessGroupApplicationStatus;
  applicationId: string | null;
  canReviewApplications: boolean;
  canManageAdmins: boolean;
};

export type AccessGroupApplication = {
  id: string;
  acgId: string;
  acgName: string;
  applicantUserId: string;
  applicantDisplayName: string;
  justification: string;
  status: Exclude<AccessGroupApplicationStatus, null>;
  submittedAt: string;
};

export type AccessGroupDirectoryUser = {
  id: string;
  username: string;
  displayName: string;
};

export type AccessGroupCataloguePage = {
  acgs: AccessGroupSummary[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};

export function listAccessGroups(page = 1): Promise<AccessGroupCataloguePage> {
  return apiRequestJson<AccessGroupCataloguePage>(
    `/api/v1/acgs/catalogue?page=${page}&pageSize=20`,
    { method: "GET" },
  );
}

export function applyForAccessGroup(acgId: string, justification: string, csrfToken: string) {
  return apiRequestJson<AccessGroupApplication>(`/api/v1/acgs/${pathSegment(acgId)}/applications`, {
    body: JSON.stringify({ justification }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export function withdrawAccessGroupApplication(acgId: string, csrfToken: string) {
  return apiRequestNoContent(`/api/v1/acgs/${pathSegment(acgId)}/applications/mine`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "DELETE",
  });
}

export type AccessGroupApplicationPage = {
  applications: AccessGroupApplication[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};

export async function listAccessGroupApplications(page = 1): Promise<AccessGroupApplicationPage> {
  return apiRequestJson<AccessGroupApplicationPage>(
    `/api/v1/acg-applications?page=${page}&pageSize=20`,
    { method: "GET" },
  );
}

export function decideAccessGroupApplication(
  application: AccessGroupApplication,
  decision: "approve" | "reject",
  reason: string,
  csrfToken: string,
) {
  return apiRequestJson<AccessGroupApplication>(
    `/api/v1/acg-applications/${pathSegment(application.id)}/decision`,
    {
      body: JSON.stringify({
        decision,
        reason: decision === "reject" ? reason : undefined,
      }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export async function listAccessGroupAdmins(acgId: string): Promise<AccessGroupDirectoryUser[]> {
  const result = await apiRequestJson<{ admins: AccessGroupDirectoryUser[] }>(
    `/api/v1/acgs/${pathSegment(acgId)}/admins`,
    { method: "GET" },
  );
  return result.admins;
}

export function addAccessGroupAdmin(acgId: string, userId: string, csrfToken: string) {
  return apiRequestJson<{ admins: AccessGroupDirectoryUser[] }>(
    `/api/v1/acgs/${pathSegment(acgId)}/admins/${pathSegment(userId)}`,
    { headers: { "X-CSRF-Token": csrfToken }, method: "PUT" },
  );
}

export function removeAccessGroupAdmin(acgId: string, userId: string, csrfToken: string) {
  return apiRequestNoContent(`/api/v1/acgs/${pathSegment(acgId)}/admins/${pathSegment(userId)}`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "DELETE",
  });
}

export async function searchAccessGroupDirectory(query: string) {
  return apiRequestJson<{
    users: AccessGroupDirectoryUser[];
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  }>(`/api/v1/acgs/admin-directory?query=${encodeURIComponent(query)}`, { method: "GET" });
}
