from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class QcDecisionStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class QcClaimStatus(StrEnum):
    AVAILABLE = "available"
    CLAIMED_BY_YOU = "claimed_by_you"
    CLAIMED = "claimed"


class ProductIndexStatus(StrEnum):
    QUEUED = "queued"
    INDEXED = "indexed"


class FeedbackRequestStatus(StrEnum):
    REQUESTED = "requested"
    SUBMITTED = "submitted"


class QcAgentPreflightStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class QcAgentCheck:
    key: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class QcAgentFinding:
    finding_id: UUID
    category: str
    severity: str
    original_text: str
    suggested_text: str
    location: str
    detail: str
    confidence: float
    blocking: bool


@dataclass(frozen=True)
class QcAgentPreflight:
    preflight_id: UUID
    ticket_id: UUID
    draft_version_id: UUID
    input_hash: str
    status: QcAgentPreflightStatus
    checks: tuple[QcAgentCheck, ...]
    blockers: tuple[str, ...]
    policy_version: str
    created_at: datetime
    findings: tuple[QcAgentFinding, ...] = ()


@dataclass(frozen=True)
class QcChecklistItem:
    key: str
    passed: bool


@dataclass(frozen=True)
class QcDecision:
    decision_id: UUID
    ticket_id: UUID
    status: QcDecisionStatus
    reason: str
    reviewer_user_id: UUID
    checklist: tuple[QcChecklistItem, ...]
    created_at: datetime


@dataclass(frozen=True)
class ProductIndexRecord:
    index_id: UUID
    ticket_id: UUID
    product_id: UUID
    status: ProductIndexStatus
    summary: str
    created_at: datetime


@dataclass(frozen=True)
class FeedbackRequest:
    request_id: UUID
    ticket_id: UUID
    product_id: UUID
    requester_user_id: UUID
    status: FeedbackRequestStatus
    created_at: datetime


@dataclass(frozen=True)
class FeedbackSubmission:
    submission_id: UUID
    request_id: UUID
    ticket_id: UUID
    product_id: UUID
    requester_user_id: UUID
    rating: int
    comment: str
    follow_up_requested: bool
    created_at: datetime
