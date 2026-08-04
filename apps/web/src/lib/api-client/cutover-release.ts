import { apiRequestJson } from "./client";

export const CUTOVER_SLICES = ["organisation", "calendar", "task_capacity"] as const;
export type CutoverSlice = (typeof CUTOVER_SLICES)[number];
type CutoverStatus = "not_previewed" | "previewed" | "approved" | "active";
export type CutoverApprovalRole = "security_review" | "release_authority";

export type CutoverManifest = {
  sourceRevision: string;
  schemaHead: string;
  organisationParityHash: string;
  calendarParityHash: string;
  taskCapacityParityHash: string;
  routingEvaluationRelease: string;
  routingEvaluationHash: string;
  protectedChecksReference: string;
  protectedChecksHash: string;
  browserEvidenceHash: string;
  securityReviewReference: string;
  securityReviewHash: string;
  backupRestoreHash: string;
};

export type CutoverApproval = {
  approvalId: string;
  slice: CutoverSlice;
  candidateDigest: string;
  previewDigest: string;
  approvalRole: CutoverApprovalRole;
  approvedByUserId: string;
  approvedAt: string;
};

export type CutoverSliceState = {
  slice: CutoverSlice;
  status: CutoverStatus;
  previewDigest: string | null;
  proposedByUserId: string | null;
  approvals: CutoverApproval[];
  activatedByUserId: string | null;
  activatedAt: string | null;
};

export type CutoverReleaseState = {
  candidateDigest: string | null;
  manifest: CutoverManifest | null;
  slices: CutoverSliceState[];
  eligible: boolean;
};

export type CutoverPreview = {
  slice: CutoverSlice;
  candidateDigest: string;
  previewDigest: string;
  proposedByUserId: string;
  expiresAt: string;
};

const DIGEST = /^[0-9a-f]{64}$/;
const STATUSES = new Set<CutoverStatus>(["not_previewed", "previewed", "approved", "active"]);
const ROLES = new Set<CutoverApprovalRole>(["security_review", "release_authority"]);

export async function getCutoverRelease(): Promise<CutoverReleaseState> {
  const value = await apiRequestJson<unknown>("/api/v1/admin/organisation/cutover-release", {
    method: "GET",
  });
  return validateRelease(value);
}

export function previewCutoverSlice(
  slice: CutoverSlice,
  manifest: CutoverManifest,
  csrfToken: string,
): Promise<CutoverPreview> {
  return postCutover<CutoverPreview>(`previews/${slice}`, manifest, csrfToken);
}

export function approveCutoverSlice(
  request: {
    slice: CutoverSlice;
    candidateDigest: string;
    previewDigest: string;
    approvalRole: CutoverApprovalRole;
    currentPassword: string;
  },
  csrfToken: string,
): Promise<CutoverApproval> {
  return postCutover<CutoverApproval>("approvals", request, csrfToken);
}

function postCutover<T>(path: string, body: object, csrfToken: string): Promise<T> {
  return apiRequestJson<T>(`/api/v1/admin/organisation/cutover-release/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify(body),
  });
}

function validateRelease(value: unknown): CutoverReleaseState {
  if (!isRecord(value) || !Array.isArray(value.slices) || typeof value.eligible !== "boolean") {
    throw new Error("The release status is incomplete. No cutover action is available.");
  }
  const candidate = nullableString(value.candidateDigest);
  const manifest = validateManifest(value.manifest);
  const slices = value.slices.map(validateSlice);
  const exactSlices =
    slices.length === CUTOVER_SLICES.length &&
    CUTOVER_SLICES.every((slice) => slices.filter((item) => item.slice === slice).length === 1);
  if (!exactSlices || (candidate !== null && !DIGEST.test(candidate))) return invalidRelease();
  if ((candidate === null) !== (manifest === null)) return invalidRelease();
  if (candidate === null) {
    if (value.eligible || slices.some((slice) => slice.status !== "not_previewed")) {
      return invalidRelease();
    }
  } else if (slices.some((slice) => !validSliceLineage(slice, candidate))) {
    return invalidRelease();
  }
  if (value.eligible && slices.some((slice) => slice.status !== "active")) return invalidRelease();
  return { candidateDigest: candidate, manifest, slices, eligible: value.eligible };
}

function validateSlice(value: unknown): CutoverSliceState {
  if (!isRecord(value) || !CUTOVER_SLICES.includes(value.slice as CutoverSlice)) {
    return invalidSlice();
  }
  if (typeof value.status !== "string" || !STATUSES.has(value.status as CutoverStatus)) {
    return invalidSlice();
  }
  if (!Array.isArray(value.approvals)) return invalidSlice();
  return {
    slice: value.slice as CutoverSlice,
    status: value.status as CutoverStatus,
    previewDigest: nullableString(value.previewDigest),
    proposedByUserId: nullableString(value.proposedByUserId),
    approvals: value.approvals.map(validateApproval),
    activatedByUserId: nullableString(value.activatedByUserId),
    activatedAt: nullableString(value.activatedAt),
  };
}

function validateApproval(value: unknown): CutoverApproval {
  if (
    !isRecord(value) ||
    !CUTOVER_SLICES.includes(value.slice as CutoverSlice) ||
    !ROLES.has(value.approvalRole as CutoverApprovalRole)
  ) {
    return invalidApproval();
  }
  return {
    approvalId: requiredString(value.approvalId),
    slice: value.slice as CutoverSlice,
    candidateDigest: requiredString(value.candidateDigest),
    previewDigest: requiredString(value.previewDigest),
    approvalRole: value.approvalRole as CutoverApprovalRole,
    approvedByUserId: requiredString(value.approvedByUserId),
    approvedAt: requiredString(value.approvedAt),
  };
}

function validSliceLineage(slice: CutoverSliceState, candidate: string): boolean {
  if (slice.status === "not_previewed") {
    return (
      slice.previewDigest === null &&
      slice.proposedByUserId === null &&
      slice.approvals.length === 0
    );
  }
  if (!slice.previewDigest || !DIGEST.test(slice.previewDigest) || !slice.proposedByUserId)
    return false;
  const actors = new Set([slice.proposedByUserId]);
  for (const approval of slice.approvals) {
    if (
      !approval.approvalId ||
      approval.slice !== slice.slice ||
      approval.candidateDigest !== candidate ||
      approval.previewDigest !== slice.previewDigest ||
      !DIGEST.test(approval.candidateDigest) ||
      !DIGEST.test(approval.previewDigest) ||
      actors.has(approval.approvedByUserId)
    )
      return false;
    actors.add(approval.approvedByUserId);
  }
  if (new Set(slice.approvals.map((item) => item.approvalRole)).size !== slice.approvals.length)
    return false;
  if (["approved", "active"].includes(slice.status) && slice.approvals.length !== 2) return false;
  return slice.status !== "active" || Boolean(slice.activatedByUserId && slice.activatedAt);
}

function validateManifest(value: unknown): CutoverManifest | null {
  if (value === null) return null;
  if (!isRecord(value)) return invalidManifest();
  const fields = [
    "sourceRevision",
    "schemaHead",
    "organisationParityHash",
    "calendarParityHash",
    "taskCapacityParityHash",
    "routingEvaluationRelease",
    "routingEvaluationHash",
    "protectedChecksReference",
    "protectedChecksHash",
    "browserEvidenceHash",
    "securityReviewReference",
    "securityReviewHash",
    "backupRestoreHash",
  ] as const;
  if (fields.some((field) => typeof value[field] !== "string")) return invalidManifest();
  return Object.fromEntries(fields.map((field) => [field, value[field]])) as CutoverManifest;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
function nullableString(value: unknown): string | null {
  return value === null ? null : requiredString(value);
}
function requiredString(value: unknown): string {
  return typeof value === "string" && value.length > 0 ? value : "";
}
function invalidRelease(): never {
  throw new Error("The release status is inconsistent. No cutover action is available.");
}
function invalidSlice(): never {
  throw new Error("A release slice has an invalid status.");
}
function invalidApproval(): never {
  throw new Error("Release approval evidence is invalid.");
}
function invalidManifest(): never {
  throw new Error("The release manifest is invalid.");
}
