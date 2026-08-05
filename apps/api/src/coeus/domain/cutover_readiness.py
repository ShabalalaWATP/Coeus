"""Safe, read-only organisation cutover readiness results."""

from dataclasses import dataclass
from enum import StrEnum


class CutoverCheckCode(StrEnum):
    MIGRATION_HEAD = "migration_head"
    ORGANISATION_TOPOLOGY = "organisation_topology"
    IDENTITY_PROJECTION = "identity_projection"
    IDENTITY_REFERENCE_PARITY = "identity_reference_parity"
    BLOCKING_FINDINGS = "blocking_findings"
    WORKFLOW_OWNERSHIP = "workflow_ownership"
    PACKAGE_INTEGRITY = "package_integrity"
    RESERVATION_INTEGRITY = "reservation_integrity"
    ROUTING_LEAF_COVERAGE = "routing_leaf_coverage"
    ROUTING_CAPABILITY_MAPPINGS = "routing_capability_mappings"
    JIOC_SERVICE_GRANT = "jioc_service_grant"
    ROUTING_APPROVAL_EVIDENCE = "routing_approval_evidence"
    BROWSER_EVIDENCE = "browser_evidence"
    CI_EVIDENCE = "ci_evidence"
    SECURITY_EVIDENCE = "security_evidence"


class CutoverCheckStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True)
class CutoverReadinessCheck:
    code: CutoverCheckCode
    status: CutoverCheckStatus
    observed_count: int
    required_count: int

    def __post_init__(self) -> None:
        if self.observed_count < 0 or self.required_count < 0:
            raise ValueError("cutover readiness counts cannot be negative")


@dataclass(frozen=True)
class CutoverReadinessReport:
    ready: bool
    checks: tuple[CutoverReadinessCheck, ...]
