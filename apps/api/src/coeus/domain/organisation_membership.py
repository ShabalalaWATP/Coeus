"""Previewed single-home organisation membership commands."""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation import MembershipRole
from coeus.domain.organisation_validation import aware, text_value


class MembershipOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    END = "end"


class MembershipCommandDenied(PermissionError):
    pass


class MembershipCommandConflict(RuntimeError):
    pass


class MembershipIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class MembershipMutationRequest:
    operation: MembershipOperation
    membership_id: UUID
    user_id: UUID
    unit_id: UUID
    expected_version: int
    role: MembershipRole
    assignment_eligible: bool
    valid_from: datetime
    valid_until: datetime | None
    authorising_grant_id: UUID
    reason: str

    def __post_init__(self) -> None:
        aware(self.valid_from, "valid_from")
        aware(self.valid_until, "valid_until")
        text_value(self.reason, "reason", 500)
        if self.operation is MembershipOperation.CREATE and self.expected_version != 0:
            raise ValueError("create expected_version must be zero")
        if self.operation is not MembershipOperation.CREATE and self.expected_version < 1:
            raise ValueError("update and end expected_version must be positive")
        if self.operation is MembershipOperation.END and self.valid_until is None:
            raise ValueError("end requires valid_until")
        if self.operation is not MembershipOperation.END and self.valid_until is not None:
            raise ValueError("only end may set valid_until")
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must follow valid_from")
        if self.operation is MembershipOperation.END and self.assignment_eligible:
            raise ValueError("an ended membership cannot remain assignment eligible")


@dataclass(frozen=True)
class MembershipMutationSnapshot:
    unit_version: int
    current_membership_version: int
    active_task_legs: int
    state_digest: str

    def __post_init__(self) -> None:
        if self.unit_version < 1 or self.current_membership_version < 0:
            raise ValueError("snapshot versions are invalid")
        if self.active_task_legs < 0:
            raise ValueError("active_task_legs cannot be negative")
        _digest(self.state_digest, "state_digest")


@dataclass(frozen=True)
class MembershipMutationPreview:
    request: MembershipMutationRequest
    snapshot: MembershipMutationSnapshot
    preview_hash: str

    def __post_init__(self) -> None:
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class MembershipMutationCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: MembershipMutationRequest
    preview_hash: str

    def __post_init__(self) -> None:
        if not self.idempotency_key or self.idempotency_key != self.idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty and trimmed")
        if len(self.idempotency_key) > 128 or any(
            ord(character) < 32 for character in self.idempotency_key
        ):
            raise ValueError("idempotency_key is invalid")
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class MembershipMutationResult:
    membership_id: UUID
    version: int
    replayed: bool = False


def membership_hash(
    request: MembershipMutationRequest,
    actor_user_id: UUID,
    snapshot: MembershipMutationSnapshot,
) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "request": _serialise(vars(request)),
        "snapshot": _serialise(vars(snapshot)),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _serialise(values: dict[str, object]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in values.items():
        if isinstance(value, (UUID, datetime)):
            output[key] = str(value)
        elif isinstance(value, StrEnum):
            output[key] = value.value
        else:
            output[key] = value
    return output


def _digest(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
