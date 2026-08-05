"""Commands and outcomes for the disabled organisation grant authority."""

import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation import ManagementAction


class OrganisationAuthorityDenied(PermissionError):
    pass


class OrganisationAuthorityConflict(RuntimeError):
    pass


class OrganisationIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    evidence_grant_id: UUID | None
    reason: str


@dataclass(frozen=True)
class CreateManagementGrantCommand:
    command_id: UUID
    grant_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    manager_user_id: UUID
    root_unit_id: UUID
    action: ManagementAction
    include_descendants: bool
    source_grant_id: UUID
    expected_source_version: int
    reason: str
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        _key(self.idempotency_key)
        _reason(self.reason)
        if self.expected_source_version < 1:
            raise ValueError("expected_source_version must be positive")
        if self.valid_until is not None and self.valid_until.utcoffset() is None:
            raise ValueError("valid_until must be timezone-aware")


@dataclass(frozen=True)
class RevokeManagementGrantCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    grant_id: UUID
    expected_version: int
    reason: str

    def __post_init__(self) -> None:
        _key(self.idempotency_key)
        _reason(self.reason)
        if self.expected_version < 1:
            raise ValueError("expected_version must be positive")


@dataclass(frozen=True)
class GrantCommandResult:
    grant_id: UUID
    version: int
    replayed: bool = False


def command_hash(command: CreateManagementGrantCommand | RevokeManagementGrantCommand) -> str:
    payload = {key: _json_value(item) for key, item in vars(command).items()}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _json_value(value: object) -> object:
    if isinstance(value, ManagementAction):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _key(value: str) -> None:
    if not value or value != value.strip() or len(value) > 128:
        raise ValueError("idempotency_key must contain 1 to 128 trimmed characters")
    if any(ord(character) < 32 for character in value):
        raise ValueError("idempotency_key cannot contain control characters")


def _reason(value: str) -> None:
    if not value or value != value.strip() or len(value) > 500:
        raise ValueError("reason must contain 1 to 500 trimmed characters")
    if any(ord(character) < 32 for character in value):
        raise ValueError("reason cannot contain control characters")
