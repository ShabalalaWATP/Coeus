"""Previewed fail-closed organisation unit deactivation."""

import json
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation_validation import text_value


class OrganisationDeactivationDenied(PermissionError):
    pass


class OrganisationDeactivationConflict(RuntimeError):
    pass


class OrganisationDeactivationIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class OrganisationDeactivationRequest:
    unit_id: UUID
    expected_version: int
    authorising_grant_id: UUID
    reason: str

    def __post_init__(self) -> None:
        if self.expected_version < 1:
            raise ValueError("expected_version must be positive")
        text_value(self.reason, "reason", 500)


@dataclass(frozen=True)
class OrganisationDeactivationImpact:
    active_children: int
    active_descendants: int
    memberships: int
    direct_grants: int
    delivery_profiles: int
    capability_mappings: int
    active_task_legs: int
    reservations: int
    team_calendar_events: int
    pending_transfers: int
    saved_views: int
    state_digest: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, int) or value < 0
            for key, value in vars(self).items()
            if key != "state_digest"
        ):
            raise ValueError("deactivation impact counts must be non-negative integers")
        _digest(self.state_digest, "state_digest")

    @property
    def blocking_count(self) -> int:
        return sum(value for key, value in vars(self).items() if key != "state_digest")


@dataclass(frozen=True)
class OrganisationDeactivationPreview:
    request: OrganisationDeactivationRequest
    impact: OrganisationDeactivationImpact
    preview_hash: str

    def __post_init__(self) -> None:
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class OrganisationDeactivationCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: OrganisationDeactivationRequest
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
class OrganisationDeactivationResult:
    unit_id: UUID
    version: int
    replayed: bool = False


def deactivation_hash(
    request: OrganisationDeactivationRequest,
    actor_user_id: UUID,
    impact: OrganisationDeactivationImpact,
) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "request": {
            key: str(value) if isinstance(value, UUID) else value
            for key, value in vars(request).items()
        },
        "impact": vars(impact),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _digest(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
