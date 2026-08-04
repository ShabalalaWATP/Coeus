"""Reviewed accountable-owner handover and reservation dispositions."""

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID


class ReservationDisposition(StrEnum):
    RELEASE = "release"
    REPLACE = "replace"


class WorkPackageHandoverDenied(PermissionError):
    pass


class WorkPackageHandoverConflict(ValueError):
    pass


@dataclass(frozen=True)
class ReservationHandover:
    source_reservation_id: UUID
    expected_source_version: int
    disposition: ReservationDisposition
    replacement_reservation_id: UUID | None = None
    replacement_idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if self.expected_source_version < 1:
            raise ValueError("source reservation version must be positive")
        replacement = self.disposition is ReservationDisposition.REPLACE
        if replacement != (self.replacement_reservation_id is not None):
            raise ValueError("replacement reservation identity must match its disposition")
        if replacement != (self.replacement_idempotency_key is not None):
            raise ValueError("replacement idempotency key must match its disposition")
        if self.replacement_idempotency_key is not None and not (
            1 <= len(self.replacement_idempotency_key) <= 128
        ):
            raise ValueError("replacement idempotency key is invalid")


@dataclass(frozen=True)
class WorkPackageHandoverRequest:
    unit_id: UUID
    package_id: UUID
    target_user_id: UUID
    expected_package_version: int
    expected_ownership_version: int
    authorising_grant_id: UUID
    expected_grant_version: int
    target_membership_id: UUID
    expected_target_membership_version: int
    expected_target_account_credential_version: int
    expected_target_account_source_hash: str
    expected_ticket_version: int
    expected_ticket_source_hash: str
    reservations: tuple[ReservationHandover, ...]

    def __post_init__(self) -> None:
        versions = (
            self.expected_package_version,
            self.expected_ownership_version,
            self.expected_grant_version,
            self.expected_target_membership_version,
            self.expected_ticket_version,
        )
        if min(versions) < 1 or self.expected_target_account_credential_version < 0:
            raise ValueError("handover evidence versions are invalid")
        if len(self.expected_target_account_source_hash) != 64 or any(
            char not in "0123456789abcdef" for char in self.expected_target_account_source_hash
        ):
            raise ValueError("target account source hash is invalid")
        if len(self.expected_ticket_source_hash) != 64 or any(
            char not in "0123456789abcdef" for char in self.expected_ticket_source_hash
        ):
            raise ValueError("ticket source hash is invalid")
        source_ids = [item.source_reservation_id for item in self.reservations]
        replacement_ids = [
            item.replacement_reservation_id
            for item in self.reservations
            if item.replacement_reservation_id is not None
        ]
        if len(source_ids) > 64:
            raise ValueError("handover reservation inventory is too large")
        if len(set(source_ids)) != len(source_ids) or len(set(replacement_ids)) != len(
            replacement_ids
        ):
            raise ValueError("handover reservation identities must be unique")


@dataclass(frozen=True)
class WorkPackageHandoverPreview:
    preview_hash: str
    package_id: UUID
    source_user_id: UUID
    target_user_id: UUID
    package_version: int
    planned_package_version: int
    participant_count: int
    reservation_count: int
    dependency_count: int


@dataclass(frozen=True)
class HandoverWorkPackageCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: WorkPackageHandoverRequest
    preview_hash: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.idempotency_key) <= 128:
            raise ValueError("handover idempotency key is invalid")
        if len(self.preview_hash) != 64:
            raise ValueError("handover preview hash is invalid")


@dataclass(frozen=True)
class WorkPackageHandoverResult:
    package_id: UUID
    source_user_id: UUID
    target_user_id: UUID
    package_version: int
    released_reservation_count: int
    replacement_reservation_count: int
    replayed: bool


def handover_request_hash(actor_user_id: UUID, request: WorkPackageHandoverRequest) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "authorising_grant_id": str(request.authorising_grant_id),
        "expected_grant_version": request.expected_grant_version,
        "expected_ownership_version": request.expected_ownership_version,
        "expected_package_version": request.expected_package_version,
        "expected_target_account_credential_version": (
            request.expected_target_account_credential_version
        ),
        "expected_target_account_source_hash": request.expected_target_account_source_hash,
        "expected_ticket_version": request.expected_ticket_version,
        "expected_ticket_source_hash": request.expected_ticket_source_hash,
        "expected_target_membership_version": request.expected_target_membership_version,
        "package_id": str(request.package_id),
        "reservations": [
            {
                "disposition": item.disposition.value,
                "expected_source_version": item.expected_source_version,
                "replacement_idempotency_key": item.replacement_idempotency_key,
                "replacement_reservation_id": (
                    str(item.replacement_reservation_id)
                    if item.replacement_reservation_id is not None
                    else None
                ),
                "source_reservation_id": str(item.source_reservation_id),
            }
            for item in request.reservations
        ],
        "target_membership_id": str(request.target_membership_id),
        "target_user_id": str(request.target_user_id),
        "unit_id": str(request.unit_id),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def handover_preview_hash(request_hash: str, inventory: dict[str, object]) -> str:
    encoded = json.dumps(
        {"inventory": inventory, "request_hash": request_hash},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return sha256(encoded).hexdigest()
