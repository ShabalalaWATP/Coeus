import { apiRequestJson } from "./client";

export type CutoverReadinessCheckCode =
  | "migration_head"
  | "organisation_topology"
  | "identity_projection"
  | "identity_reference_parity"
  | "blocking_findings"
  | "workflow_ownership"
  | "package_integrity"
  | "reservation_integrity"
  | "routing_leaf_coverage"
  | "routing_capability_mappings"
  | "jioc_service_grant"
  | "routing_approval_evidence"
  | "browser_evidence"
  | "ci_evidence"
  | "security_evidence";

export type CutoverReadinessCheck = {
  code: CutoverReadinessCheckCode;
  status: "passed" | "blocked" | "error";
  observedCount: number;
  requiredCount: number;
};

export type CutoverReadiness = {
  ready: boolean;
  checks: CutoverReadinessCheck[];
};

export function getCutoverReadiness(): Promise<CutoverReadiness> {
  return apiRequestJson<CutoverReadiness>("/api/v1/admin/organisation/cutover-readiness", {
    method: "GET",
  });
}
