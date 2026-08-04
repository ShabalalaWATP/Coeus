"""Preview and command records for safe organisation reparenting."""

import json
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation_validation import text_value


class OrganisationReparentDenied(PermissionError):
    pass


class OrganisationReparentConflict(RuntimeError):
    pass


class OrganisationReparentIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class OrganisationReparentRequest:
    unit_id: UUID
    new_parent_unit_id: UUID
    expected_unit_version: int
    expected_parent_version: int
    authorising_grant_id: UUID
    reason: str

    def __post_init__(self) -> None:
        if self.unit_id == self.new_parent_unit_id:
            raise ValueError("an organisation unit cannot parent itself")
        if self.expected_unit_version < 1 or self.expected_parent_version < 1:
            raise ValueError("expected versions must be positive")
        text_value(self.reason, "reason", 500)


@dataclass(frozen=True)
class OrganisationReparentImpact:
    source_parent_unit_id: UUID
    source_topology_revision_id: UUID
    descendants: int
    memberships: int
    grants: int
    capability_mappings: int
    active_task_legs: int
    reservations: int
    team_calendar_events: int
    pending_transfers: int
    saved_views: int
    newly_covering_grants: int
    maximum_result_depth: int
    state_digest: str

    def __post_init__(self) -> None:
        counts = vars(self).copy()
        counts.pop("source_parent_unit_id")
        counts.pop("source_topology_revision_id")
        counts.pop("state_digest")
        if any(not isinstance(value, int) or value < 0 for value in counts.values()):
            raise ValueError("reparent impact counts must be non-negative integers")
        _digest(self.state_digest, "state_digest")


@dataclass(frozen=True)
class OrganisationReparentPreview:
    unit_id: UUID
    new_parent_unit_id: UUID
    impact: OrganisationReparentImpact
    preview_hash: str

    def __post_init__(self) -> None:
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class OrganisationReparentCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: OrganisationReparentRequest
    preview_hash: str

    def __post_init__(self) -> None:
        if not self.idempotency_key or self.idempotency_key != self.idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty and trimmed")
        if len(self.idempotency_key) > 128:
            raise ValueError("idempotency_key cannot exceed 128 characters")
        if any(ord(character) < 32 for character in self.idempotency_key):
            raise ValueError("idempotency_key cannot contain control characters")
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class OrganisationReparentResult:
    unit_id: UUID
    parent_unit_id: UUID
    version: int
    topology_revision_id: UUID
    replayed: bool = False


def reparent_hash(
    request: OrganisationReparentRequest,
    actor_user_id: UUID,
    impact: OrganisationReparentImpact,
) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "request": _serialise(vars(request)),
        "impact": _serialise(vars(impact)),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _serialise(values: dict[str, object]) -> dict[str, object]:
    return {key: str(value) if isinstance(value, UUID) else value for key, value in values.items()}


def _digest(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
