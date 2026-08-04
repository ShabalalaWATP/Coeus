"""Reviewed, version-bound contributor lifecycle contracts."""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID


class ContributorOperation(StrEnum):
    ADD = "add"
    END = "end"


class WorkPackageContributorDenied(PermissionError):
    pass


class WorkPackageContributorConflict(ValueError):
    pass


@dataclass(frozen=True)
class ContributorCapacityPlan:
    reservation_id: UUID
    starts_at: datetime
    ends_at: datetime
    reserved_minutes: int
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("contributor capacity bounds must be timezone-aware")
        if self.starts_at >= self.ends_at:
            raise ValueError("contributor capacity end must follow its start")
        if self.reserved_minutes <= 0 or self.reserved_minutes % 15:
            raise ValueError("contributor capacity must use positive 15-minute increments")
        if not 1 <= len(self.idempotency_key) <= 128:
            raise ValueError("contributor capacity idempotency key is invalid")


@dataclass(frozen=True)
class ContributorChangeRequest:
    unit_id: UUID
    package_id: UUID
    contributor_user_id: UUID
    operation: ContributorOperation
    expected_package_version: int
    expected_ownership_version: int
    authorising_grant_id: UUID
    expected_grant_version: int
    membership_id: UUID
    expected_membership_version: int
    expected_account_credential_version: int
    expected_account_source_hash: str
    capacity_plan: ContributorCapacityPlan | None = None

    def __post_init__(self) -> None:
        if (
            min(
                self.expected_package_version,
                self.expected_ownership_version,
                self.expected_grant_version,
                self.expected_membership_version,
            )
            < 1
        ):
            raise ValueError("contributor evidence versions must be positive")
        if self.expected_account_credential_version < 0:
            raise ValueError("account credential version cannot be negative")
        if len(self.expected_account_source_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.expected_account_source_hash
        ):
            raise ValueError("account source hash is invalid")
        if self.operation is ContributorOperation.END and self.capacity_plan is not None:
            raise ValueError("ending a contributor cannot create capacity")


@dataclass(frozen=True)
class ContributorChangePreview:
    preview_hash: str
    package_id: UUID
    package_version: int
    ownership_version: int
    contributor_user_id: UUID
    contributor_active: bool
    planned_package_version: int


@dataclass(frozen=True)
class ChangeContributorCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: ContributorChangeRequest
    preview_hash: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.idempotency_key) <= 128:
            raise ValueError("contributor idempotency key is invalid")
        if len(self.preview_hash) != 64:
            raise ValueError("contributor preview hash is invalid")


@dataclass(frozen=True)
class ContributorChangeResult:
    package_id: UUID
    package_version: int
    contributor_user_id: UUID
    contributor_active: bool
    replayed: bool


def contributor_change_hash(actor_user_id: UUID, request: ContributorChangeRequest) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "authorising_grant_id": str(request.authorising_grant_id),
        "contributor_user_id": str(request.contributor_user_id),
        "expected_account_credential_version": request.expected_account_credential_version,
        "expected_account_source_hash": request.expected_account_source_hash,
        "expected_grant_version": request.expected_grant_version,
        "expected_membership_version": request.expected_membership_version,
        "expected_ownership_version": request.expected_ownership_version,
        "expected_package_version": request.expected_package_version,
        "membership_id": str(request.membership_id),
        "operation": request.operation.value,
        "package_id": str(request.package_id),
        "unit_id": str(request.unit_id),
        "capacity_plan": _capacity_payload(request.capacity_plan),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _capacity_payload(plan: ContributorCapacityPlan | None) -> dict[str, object] | None:
    if plan is None:
        return None
    return {
        "reservation_id": str(plan.reservation_id),
        "starts_at": plan.starts_at.isoformat(),
        "ends_at": plan.ends_at.isoformat(),
        "reserved_minutes": plan.reserved_minutes,
        "idempotency_key": plan.idempotency_key,
    }
