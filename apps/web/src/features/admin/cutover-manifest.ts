import type { CutoverManifest } from "../../lib/api-client/cutover-release";

export const EMPTY_CUTOVER_MANIFEST: CutoverManifest = {
  sourceRevision: "",
  schemaHead: "",
  organisationParityHash: "",
  calendarParityHash: "",
  taskCapacityParityHash: "",
  routingEvaluationRelease: "",
  routingEvaluationHash: "",
  protectedChecksReference: "",
  protectedChecksHash: "",
  browserEvidenceHash: "",
  securityReviewReference: "",
  securityReviewHash: "",
  backupRestoreHash: "",
};

export const REFERENCE_FIELDS = [
  ["sourceRevision", "Source revision"],
  ["schemaHead", "Database schema revision"],
  ["routingEvaluationRelease", "Routing evaluation release"],
  ["protectedChecksReference", "Protected checks reference"],
  ["securityReviewReference", "Security review reference"],
] as const;

export const HASH_FIELDS = [
  ["organisationParityHash", "Organisation parity evidence"],
  ["calendarParityHash", "Calendar parity evidence"],
  ["taskCapacityParityHash", "Task and capacity parity evidence"],
  ["routingEvaluationHash", "Routing evaluation evidence"],
  ["protectedChecksHash", "Protected checks evidence"],
  ["browserEvidenceHash", "Browser journey evidence"],
  ["securityReviewHash", "Security review evidence"],
  ["backupRestoreHash", "Backup and restore evidence"],
] as const;

/** Every field present, and every hash field a full SHA-256 digest. */
export function isCompleteManifest(value: CutoverManifest): boolean {
  const digest = /^[0-9a-f]{64}$/;
  return (
    Object.entries(value).every(([, item]) => item.length > 0) &&
    HASH_FIELDS.every(([field]) => digest.test(value[field]))
  );
}
