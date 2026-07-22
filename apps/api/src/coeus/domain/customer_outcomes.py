"""Typed customer satisfaction and human re-analysis decisions."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class CustomerProductDecisionStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ManagerReanalysisStatus(StrEnum):
    AGREED = "agreed"
    REFERRED_TO_JIOC = "referred_to_jioc"


class JiocReanalysisStatus(StrEnum):
    REANALYSE = "reanalyse"
    CLOSE = "close"


@dataclass(frozen=True)
class CustomerProductDecision:
    decision_id: UUID
    ticket_id: UUID
    product_id: UUID
    status: CustomerProductDecisionStatus
    reason: str
    unmet_criteria: tuple[str, ...]
    actor_user_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class ManagerReanalysisDecision:
    decision_id: UUID
    ticket_id: UUID
    customer_decision_id: UUID
    status: ManagerReanalysisStatus
    rationale: str
    actor_user_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class JiocReanalysisDecision:
    decision_id: UUID
    ticket_id: UUID
    manager_decision_id: UUID
    status: JiocReanalysisStatus
    rationale: str
    actor_user_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class ProductOutcomeHistory:
    customer_decisions: tuple[CustomerProductDecision, ...] = ()
    manager_decisions: tuple[ManagerReanalysisDecision, ...] = ()
    jioc_decisions: tuple[JiocReanalysisDecision, ...] = ()
