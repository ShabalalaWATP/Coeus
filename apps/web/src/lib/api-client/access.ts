import { apiRequestJson, apiRequestNoContent, pathSegment } from "./client";

export type AccessControlGroup = {
  id: string;
  code: string;
  name: string;
  description: string;
  ownerUserId: string | null;
  isActive: boolean;
  memberUserIds: string[];
  members?: { id: string; displayName: string; username: string }[];
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

export async function listAcgs(): Promise<AccessControlGroup[]> {
  const response = await apiRequestJson<{ acgs: AccessControlGroup[] }>("/api/v1/acgs", {
    method: "GET",
  });
  return response.acgs;
}

export function createAcg(
  payload: CreateAccessControlGroupRequest,
  csrfToken: string,
): Promise<AccessControlGroup> {
  return apiRequestJson<AccessControlGroup>("/api/v1/acgs", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export function updateAcg(
  acgId: string,
  payload: UpdateAccessControlGroupRequest,
  csrfToken: string,
): Promise<AccessControlGroup> {
  return apiRequestJson<AccessControlGroup>(`/api/v1/acgs/${pathSegment(acgId)}`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PATCH",
  });
}

export function addAcgMember(
  acgId: string,
  userId: string,
  csrfToken: string,
): Promise<AccessControlGroup> {
  return apiRequestJson<AccessControlGroup>(`/api/v1/acgs/${pathSegment(acgId)}/members`, {
    body: JSON.stringify({ userId }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export function removeAcgMember(acgId: string, userId: string, csrfToken: string): Promise<void> {
  return apiRequestNoContent(`/api/v1/acgs/${pathSegment(acgId)}/members/${pathSegment(userId)}`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "DELETE",
  });
}
