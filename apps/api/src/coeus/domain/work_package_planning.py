"""Actor-bound work-package planning and capacity reservation contracts."""

import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from coeus.domain.work_packages import CapacityReservation


class WorkPackagePlanningDenied(PermissionError):
    pass


class WorkPackagePlanningConflict(ValueError):
    pass


@dataclass(frozen=True)
class WorkPackagePlanRequest:
    unit_id: UUID
    package_id: UUID
    expected_package_version: int
    expected_ownership_version: int
    accountable_user_id: UUID
    estimated_minutes: int
    remaining_minutes: int
    due_at: datetime
    priority: int
    priority_override_reason: str
    reservation_id: UUID
    starts_at: datetime
    ends_at: datetime
    reserved_minutes: int
    authorising_grant_id: UUID

    def __post_init__(self) -> None:
        _validate_effort(self)
        _validate_schedule(self)
        if self.expected_package_version < 1 or self.expected_ownership_version < 1:
            raise ValueError("expected planning versions must be positive")


def _validate_effort(request: WorkPackagePlanRequest) -> None:
    if request.estimated_minutes <= 0 or request.estimated_minutes % 15:
        raise ValueError("estimated effort must use positive 15-minute increments")
    if (
        request.remaining_minutes < 0
        or request.remaining_minutes > request.estimated_minutes
        or request.remaining_minutes % 15
    ):
        raise ValueError("remaining effort must be a bounded 15-minute value")
    if request.reserved_minutes <= 0 or request.reserved_minutes % 15:
        raise ValueError("reserved effort must use positive 15-minute increments")
    if request.reserved_minutes > request.remaining_minutes:
        raise ValueError("reserved effort cannot exceed remaining effort")


def _validate_schedule(request: WorkPackagePlanRequest) -> None:
    if not 1 <= request.priority <= 5:
        raise ValueError("priority must be between one and five")
    if len(request.priority_override_reason.strip()) > 500:
        raise ValueError("priority override reason is too long")
    for value, field in (
        (request.due_at, "due_at"),
        (request.starts_at, "starts_at"),
        (request.ends_at, "ends_at"),
    ):
        if value.tzinfo is None:
            raise ValueError(f"{field} must be timezone-aware")
    if request.starts_at >= request.ends_at or request.ends_at > request.due_at:
        raise ValueError("reservation must end after it starts and no later than the due date")


@dataclass(frozen=True)
class WorkPackagePlanningPreview:
    preview_hash: str
    package_id: UUID
    package_version: int
    ownership_version: int
    accountable_user_id: UUID
    planned_package_version: int


@dataclass(frozen=True)
class PlanWorkPackageCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: WorkPackagePlanRequest
    preview_hash: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.idempotency_key) <= 128:
            raise ValueError("planning idempotency key is invalid")
        if len(self.preview_hash) != 64:
            raise ValueError("planning preview hash is invalid")


@dataclass(frozen=True)
class WorkPackagePlanningResult:
    package_id: UUID
    package_version: int
    reservation: CapacityReservation
    replayed: bool


def planning_hash(actor_user_id: UUID, request: WorkPackagePlanRequest) -> str:
    payload = {
        "accountable_user_id": str(request.accountable_user_id),
        "actor_user_id": str(actor_user_id),
        "authorising_grant_id": str(request.authorising_grant_id),
        "due_at": request.due_at.isoformat(),
        "ends_at": request.ends_at.isoformat(),
        "estimated_minutes": request.estimated_minutes,
        "expected_ownership_version": request.expected_ownership_version,
        "expected_package_version": request.expected_package_version,
        "package_id": str(request.package_id),
        "priority": request.priority,
        "priority_override_reason": request.priority_override_reason.strip(),
        "remaining_minutes": request.remaining_minutes,
        "reservation_id": str(request.reservation_id),
        "reserved_minutes": request.reserved_minutes,
        "starts_at": request.starts_at.isoformat(),
        "unit_id": str(request.unit_id),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()
