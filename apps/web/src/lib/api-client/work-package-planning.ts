import { apiRequestJson } from "./client";

export type WorkPackagePlan = {
  expectedPackageVersion: number;
  expectedOwnershipVersion: number;
  accountableUserId: string;
  estimatedMinutes: number;
  remainingMinutes: number;
  dueAt: string;
  priority: number;
  priorityOverrideReason: string;
  reservationId: string;
  startsAt: string;
  endsAt: string;
  reservedMinutes: number;
  authorisingGrantId: string;
};

export type WorkPackagePlanningPreview = {
  previewHash: string;
  packageId: string;
  packageVersion: number;
  ownershipVersion: number;
  accountableUserId: string;
  plannedPackageVersion: number;
};

export type WorkPackagePlanningResult = {
  packageId: string;
  packageVersion: number;
  reservation: {
    reservationId: string;
    userId: string;
    packageId: string;
    startsAt: string;
    endsAt: string;
    reservedMinutes: number;
    state: string;
    version: number;
  };
  replayed: boolean;
};

function path(unitId: string, packageId: string) {
  return `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/work-packages/${encodeURIComponent(packageId)}/planning`;
}

export function previewWorkPackagePlan(
  unitId: string,
  packageId: string,
  request: WorkPackagePlan,
  csrfToken: string,
): Promise<WorkPackagePlanningPreview> {
  return apiRequestJson(`${path(unitId, packageId)}/previews`, {
    body: JSON.stringify(request),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export function executeWorkPackagePlan(
  unitId: string,
  packageId: string,
  request: WorkPackagePlan,
  previewHash: string,
  csrfToken: string,
): Promise<WorkPackagePlanningResult> {
  return apiRequestJson(`${path(unitId, packageId)}/commands`, {
    body: JSON.stringify({
      commandId: crypto.randomUUID(),
      idempotencyKey: `plan-package-${crypto.randomUUID()}`,
      request,
      previewHash,
    }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}
