"""Previewed exact-boundary single-home personnel transfers."""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation import MembershipRole
from coeus.domain.organisation_validation import aware, text_value


class PersonnelTransferStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class PersonnelTransferDenied(PermissionError):
    pass


class PersonnelTransferConflict(RuntimeError):
    pass


class PersonnelTransferIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class PersonnelTransferRequest:
    source_membership_id: UUID
    target_membership_id: UUID
    user_id: UUID
    source_unit_id: UUID
    target_unit_id: UUID
    expected_membership_version: int
    expected_target_unit_version: int
    target_role: MembershipRole
    assignment_eligible: bool
    effective_at: datetime
    source_authorising_grant_id: UUID
    target_authorising_grant_id: UUID
    reason: str

    def __post_init__(self) -> None:
        if self.source_membership_id == self.target_membership_id:
            raise ValueError("source and target membership identities must differ")
        if self.source_unit_id == self.target_unit_id:
            raise ValueError("source and target units must differ")
        if self.expected_membership_version < 1 or self.expected_target_unit_version < 1:
            raise ValueError("expected versions must be positive")
        aware(self.effective_at, "effective_at")
        text_value(self.reason, "reason", 500)


@dataclass(frozen=True)
class PersonnelTransferImpact:
    active_task_legs: int
    reservations: int
    future_team_events: int
    named_work_items: int
    state_digest: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, int) or value < 0
            for key, value in vars(self).items()
            if key != "state_digest"
        ):
            raise ValueError("transfer impact counts must be non-negative integers")
        _digest(self.state_digest, "state_digest")


@dataclass(frozen=True)
class PersonnelTransferPreview:
    request: PersonnelTransferRequest
    impact: PersonnelTransferImpact
    preview_hash: str

    def __post_init__(self) -> None:
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class PersonnelTransferCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: PersonnelTransferRequest
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
class PersonnelTransferResult:
    command_id: UUID
    source_membership_id: UUID
    target_membership_id: UUID
    status: PersonnelTransferStatus
    source_version: int
    target_version: int
    replayed: bool = False
    failure_code: str = ""


def personnel_transfer_hash(
    request: PersonnelTransferRequest,
    actor_user_id: UUID,
    impact: PersonnelTransferImpact,
) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "request": _serialise(vars(request)),
        "impact": _serialise(vars(impact)),
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
