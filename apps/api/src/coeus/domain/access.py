from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ProductStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


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
class ProjectMember:
    user_id: UUID
    role: str


@dataclass(frozen=True)
class ProjectMilestone:
    milestone_id: UUID
    title: str
    status: str


@dataclass(frozen=True)
class ProjectPlanItem:
    plan_item_id: UUID
    title: str
    owner_role: str
    status: str


@dataclass(frozen=True)
class ProjectWorkspace:
    project_id: UUID
    reference: str
    name: str
    summary: str
    requester_user_id: UUID
    acg_ids: frozenset[UUID]
    product_ids: frozenset[UUID]
    ticket_ids: frozenset[UUID]
    members: tuple[ProjectMember, ...]
    milestones: tuple[ProjectMilestone, ...]
    plan_items: tuple[ProjectPlanItem, ...]


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
