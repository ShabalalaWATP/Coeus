from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class QcDecisionStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ProductIndexStatus(StrEnum):
    QUEUED = "queued"
    INDEXED = "indexed"


class FeedbackRequestStatus(StrEnum):
    REQUESTED = "requested"
    SUBMITTED = "submitted"


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
