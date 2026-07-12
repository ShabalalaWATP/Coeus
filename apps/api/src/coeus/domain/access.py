from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ProductStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AcgApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


@dataclass
class AccessControlGroup:
    acg_id: UUID
    code: str
    name: str
    description: str
    owner_user_id: UUID | None
    is_active: bool


@dataclass(frozen=True)
class AccessControlGroupMembership:
    acg_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class AcgAccessApplication:
    application_id: UUID
    acg_id: UUID
    applicant_user_id: UUID
    justification: str
    status: AcgApplicationStatus
    submitted_at: datetime
    decided_at: datetime | None = None
    decided_by_user_id: UUID | None = None
    decision_reason: str | None = None


@dataclass(frozen=True)
class ProductRecord:
    product_id: UUID
    title: str
    summary: str
    product_type: str
    status: ProductStatus
    classification_level: int
    handling_caveats: frozenset[str]
    acg_ids: frozenset[UUID]
    owner_team: str


@dataclass(frozen=True)
class AccessCheck:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str
    checks: tuple[AccessCheck, ...]
