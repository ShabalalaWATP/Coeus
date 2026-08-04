"""Exact-candidate evidence and states for bounded-context cutover."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")


class CutoverSlice(StrEnum):
    ORGANISATION = "organisation"
    CALENDAR = "calendar"
    TASK_CAPACITY = "task_capacity"


class CutoverSliceStatus(StrEnum):
    NOT_PREVIEWED = "not_previewed"
    PREVIEWED = "previewed"
    APPROVED = "approved"
    ACTIVE = "active"


class CutoverApprovalRole(StrEnum):
    SECURITY_REVIEW = "security_review"
    RELEASE_AUTHORITY = "release_authority"


@dataclass(frozen=True)
class CutoverManifest:
    source_revision: str
    schema_head: str
    organisation_parity_hash: str
    calendar_parity_hash: str
    task_capacity_parity_hash: str
    routing_evaluation_release: str
    routing_evaluation_hash: str
    protected_checks_reference: str
    protected_checks_hash: str
    browser_evidence_hash: str
    security_review_reference: str
    security_review_hash: str
    backup_restore_hash: str

    def __post_init__(self) -> None:
        references = (
            self.source_revision,
            self.schema_head,
            self.routing_evaluation_release,
            self.protected_checks_reference,
            self.security_review_reference,
        )
        if any(not _REFERENCE.fullmatch(item) for item in references):
            raise ValueError("cutover evidence references must use the safe reference syntax")
        digests = (
            self.organisation_parity_hash,
            self.calendar_parity_hash,
            self.task_capacity_parity_hash,
            self.routing_evaluation_hash,
            self.protected_checks_hash,
            self.browser_evidence_hash,
            self.security_review_hash,
            self.backup_restore_hash,
        )
        if any(not _DIGEST.fullmatch(item) for item in digests):
            raise ValueError("cutover evidence hashes must be lower-case SHA-256 digests")

    @property
    def candidate_hash(self) -> str:
        payload = {
            "backup_restore_hash": self.backup_restore_hash,
            "browser_evidence_hash": self.browser_evidence_hash,
            "calendar_parity_hash": self.calendar_parity_hash,
            "organisation_parity_hash": self.organisation_parity_hash,
            "protected_checks_hash": self.protected_checks_hash,
            "protected_checks_reference": self.protected_checks_reference,
            "routing_evaluation_hash": self.routing_evaluation_hash,
            "routing_evaluation_release": self.routing_evaluation_release,
            "schema_head": self.schema_head,
            "security_review_hash": self.security_review_hash,
            "security_review_reference": self.security_review_reference,
            "source_revision": self.source_revision,
            "task_capacity_parity_hash": self.task_capacity_parity_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class CutoverSlicePreview:
    slice: CutoverSlice
    candidate_hash: str
    preview_hash: str
    proposed_by_user_id: UUID
    expires_at: datetime


@dataclass(frozen=True)
class CutoverSliceApproval:
    approval_id: UUID
    slice: CutoverSlice
    candidate_hash: str
    preview_hash: str
    approval_role: CutoverApprovalRole
    approved_by_user_id: UUID
    approved_at: datetime


@dataclass(frozen=True)
class CutoverSliceState:
    slice: CutoverSlice
    status: CutoverSliceStatus
    preview_hash: str | None = None
    proposed_by_user_id: UUID | None = None
    approvals: tuple[CutoverSliceApproval, ...] = ()
    activated_by_user_id: UUID | None = None
    activated_at: datetime | None = None


@dataclass(frozen=True)
class CutoverReleaseState:
    candidate_hash: str | None
    manifest: CutoverManifest | None
    slices: tuple[CutoverSliceState, ...]
    eligible: bool


@dataclass(frozen=True)
class CutoverExecutionResult:
    candidate_hash: str
    slice: CutoverSlice
    status: CutoverSliceStatus
    eligible: bool


def validate_candidate_hash(value: str) -> None:
    if not _DIGEST.fullmatch(value):
        raise ValueError("candidate hash must be a lower-case SHA-256 digest")
