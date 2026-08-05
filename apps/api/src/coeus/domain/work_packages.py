"""Canonical work-package and conserved-capacity records."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from coeus.domain.team_task_ownership import WorkflowLeg


class CanonicalWorkPackageState(StrEnum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class CapacityReservationState(StrEnum):
    HELD = "held"
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CanonicalWorkPackage:
    package_id: UUID
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    owning_unit_id: UUID
    accountable_user_id: UUID | None
    title: str
    state: CanonicalWorkPackageState
    sort_order: int
    version: int
    provenance: str
    created_at: datetime
    updated_at: datetime
    contributor_user_ids: tuple[UUID, ...] = ()
    predecessor_package_ids: tuple[UUID, ...] = ()
    estimated_minutes: int | None = None
    remaining_minutes: int | None = None
    due_at: datetime | None = None
    priority: int | None = None
    priority_override_reason: str = ""
    blocked_code: str | None = None
    blocked_note: str = ""
    review_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 3 <= len(self.title.strip()) <= 180:
            raise ValueError("work-package title must contain 3 to 180 characters")
        if self.sort_order < 0 or self.version < 1:
            raise ValueError("work-package order and version must be positive")
        _validate_effort(self.estimated_minutes, self.remaining_minutes)
        _validate_priority(self.priority, self.priority_override_reason)
        _validate_blocked(self)
        if (
            self.state
            not in {
                CanonicalWorkPackageState.PENDING,
                CanonicalWorkPackageState.CANCELLED,
            }
            and self.accountable_user_id is None
        ):
            raise ValueError("an active work package requires one accountable owner")
        if self.accountable_user_id in self.contributor_user_ids:
            raise ValueError("the accountable owner cannot also be a contributor")
        if len(set(self.contributor_user_ids)) != len(self.contributor_user_ids):
            raise ValueError("work-package contributors must be unique")
        if self.package_id in self.predecessor_package_ids:
            raise ValueError("a work package cannot depend on itself")


@dataclass(frozen=True)
class CapacityReservation:
    reservation_id: UUID
    user_id: UUID
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    package_id: UUID
    starts_at: datetime
    ends_at: datetime
    reserved_minutes: int
    state: CapacityReservationState
    idempotency_key: str
    version: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.starts_at >= self.ends_at:
            raise ValueError("capacity reservation end must follow its start")
        if self.reserved_minutes <= 0 or self.reserved_minutes % 15:
            raise ValueError("reserved capacity must use positive 15-minute increments")
        if not 1 <= len(self.idempotency_key) <= 128 or self.version < 1:
            raise ValueError("capacity reservation identity or version is invalid")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("capacity reservation expiry must follow creation")


@dataclass(frozen=True)
class ReserveCapacityCommand:
    reservation_id: UUID
    actor_user_id: UUID
    user_id: UUID
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    package_id: UUID
    starts_at: datetime
    ends_at: datetime
    reserved_minutes: int
    idempotency_key: str
    expected_package_version: int
    participant_role: str = "accountable"

    def __post_init__(self) -> None:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("capacity reservation bounds must be timezone-aware")
        if self.starts_at >= self.ends_at:
            raise ValueError("capacity reservation end must follow its start")
        if self.reserved_minutes <= 0 or self.reserved_minutes % 15:
            raise ValueError("reserved capacity must use positive 15-minute increments")
        if not 1 <= len(self.idempotency_key) <= 128:
            raise ValueError("capacity idempotency key is invalid")
        if self.expected_package_version < 1:
            raise ValueError("expected work-package version is invalid")
        if self.participant_role not in {"accountable", "contributor"}:
            raise ValueError("capacity reservation participant role is invalid")


class CapacityReservationConflict(ValueError):
    """The command is stale or reuses an idempotency identity."""


class CapacityUnavailable(ValueError):
    """The requested effort exceeds conserved personal capacity."""


class CapacityUnknown(ValueError):
    """The current evidence cannot support a safe capacity decision."""


class CapacityAuthorityDenied(PermissionError):
    """The actor lacks current scoped authority to reserve capacity."""


def validate_dependency_graph(packages: tuple[CanonicalWorkPackage, ...]) -> None:
    """Reject cross-ticket, cross-leg, missing and cyclic dependency edges."""
    by_id = {package.package_id: package for package in packages}
    if len(by_id) != len(packages):
        raise ValueError("work-package identities must be unique")
    _validate_edges(packages, by_id)
    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(package_id: UUID) -> None:
        if package_id in visiting:
            raise ValueError("work-package dependencies must be acyclic")
        if package_id in visited:
            return
        visiting.add(package_id)
        for predecessor_id in by_id[package_id].predecessor_package_ids:
            visit(predecessor_id)
        visiting.remove(package_id)
        visited.add(package_id)

    for package_id in by_id:
        visit(package_id)


def _validate_edges(
    packages: tuple[CanonicalWorkPackage, ...], by_id: dict[UUID, CanonicalWorkPackage]
) -> None:
    for package in packages:
        for predecessor_id in package.predecessor_package_ids:
            predecessor = by_id.get(predecessor_id)
            if predecessor is None:
                raise ValueError("a dependency must reference a package in the same task")
            if (
                predecessor.ticket_id != package.ticket_id
                or predecessor.workflow_leg is not package.workflow_leg
            ):
                raise ValueError("dependencies cannot cross a ticket or workflow leg")


def completion_is_allowed(
    package: CanonicalWorkPackage, packages: tuple[CanonicalWorkPackage, ...]
) -> bool:
    by_id = {candidate.package_id: candidate for candidate in packages}
    return all(
        by_id.get(predecessor_id) is not None
        and by_id[predecessor_id].state is CanonicalWorkPackageState.COMPLETE
        for predecessor_id in package.predecessor_package_ids
    )


def _validate_effort(estimated: int | None, remaining: int | None) -> None:
    if estimated is None:
        if remaining is not None:
            raise ValueError("remaining effort requires an estimate")
        return
    if estimated <= 0 or estimated % 15:
        raise ValueError("estimated effort must use positive 15-minute increments")
    if remaining is None or remaining < 0 or remaining % 15 or remaining > estimated:
        raise ValueError("remaining effort must be a bounded 15-minute value")


def _validate_priority(priority: int | None, reason: str) -> None:
    if priority is not None and not 1 <= priority <= 5:
        raise ValueError("work-package priority must be between 1 and 5")
    if len(reason) > 500:
        raise ValueError("priority override reason is too long")


def _validate_blocked(package: CanonicalWorkPackage) -> None:
    evidence = package.blocked_code is not None or bool(package.blocked_note) or package.review_at
    if package.state is CanonicalWorkPackageState.BLOCKED:
        if package.blocked_code is None or package.review_at is None:
            raise ValueError("blocked work requires a structured reason and review time")
    elif evidence:
        raise ValueError("blocking evidence is only valid while work is blocked")
    if len(package.blocked_note) > 1000:
        raise ValueError("blocked note is too long")
