import { apiRequestJson, pathSegment } from "./client";

export type RegistrationSubmission = {
  username: string;
  displayName: string;
  justification: string;
  password: string;
};

export type PendingRegistration = {
  id: string;
  username: string;
  displayName: string;
  justification: string;
  status: string;
  createdAt: string;
};

export type RegistrationList = {
  registrations: PendingRegistration[];
};

export async function submitRegistration(
  payload: RegistrationSubmission,
): Promise<{ status: string }> {
  return apiRequestJson<{ status: string }>("/api/v1/auth/register", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export async function listPendingRegistrations(): Promise<RegistrationList> {
  return apiRequestJson<RegistrationList>("/api/v1/admin/registrations", { method: "GET" });
}

export async function approveRegistration(
  registrationId: string,
  csrfToken: string,
): Promise<PendingRegistration> {
  return apiRequestJson<PendingRegistration>(
    `/api/v1/admin/registrations/${pathSegment(registrationId)}/approve`,
    { headers: { "X-CSRF-Token": csrfToken }, method: "POST" },
  );
}

export async function rejectRegistration(
  registrationId: string,
  reason: string,
  csrfToken: string,
): Promise<PendingRegistration> {
  return apiRequestJson<PendingRegistration>(
    `/api/v1/admin/registrations/${pathSegment(registrationId)}/reject`,
    {
      body: JSON.stringify({ reason }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}
