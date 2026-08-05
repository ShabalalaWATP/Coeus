"""Previewed, local-only synthetic organisation fixture command records."""

import json
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID


class SyntheticFixtureUnavailable(RuntimeError):
    pass


class SyntheticFixtureConflict(RuntimeError):
    pass


class SyntheticFixtureIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class SyntheticFixtureUser:
    username: str
    user_id: UUID
    is_active: bool


@dataclass(frozen=True)
class SyntheticFixtureFinding:
    code: str
    entity_type: str
    entity_key: str
    message: str


@dataclass(frozen=True)
class SyntheticFixtureCounts:
    units: int = 0
    delivery_profiles: int = 0
    memberships: int = 0
    working_patterns: int = 0
    grants: int = 0
    team_capabilities: int = 0
    competencies: int = 0
    calendar_events: int = 0
    tasks: int = 0
    task_ownership: int = 0
    work_packages: int = 0
    capacity_reservations: int = 0

    @property
    def total(self) -> int:
        return sum(vars(self).values())


@dataclass(frozen=True)
class SyntheticFixturePreview:
    manifest_version: str
    preview_hash: str
    creates: SyntheticFixtureCounts
    unchanged: SyntheticFixtureCounts
    findings: tuple[SyntheticFixtureFinding, ...]

    @property
    def can_apply(self) -> bool:
        return not self.findings


@dataclass(frozen=True)
class SyntheticFixtureCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    preview_hash: str

    def __post_init__(self) -> None:
        if not self.idempotency_key or self.idempotency_key != self.idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty and trimmed")
        if len(self.idempotency_key) > 128:
            raise ValueError("idempotency_key cannot exceed 128 characters")
        if any(ord(character) < 32 for character in self.idempotency_key):
            raise ValueError("idempotency_key cannot contain control characters")
        if len(self.preview_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.preview_hash
        ):
            raise ValueError("preview_hash must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class SyntheticFixtureResult:
    command_id: UUID
    manifest_version: str
    created: SyntheticFixtureCounts
    replayed: bool = False
    reconciled_rows: int = 0


def fixture_preview_hash(
    actor_user_id: UUID,
    manifest_version: str,
    state_material: object,
) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "manifest_version": manifest_version,
        "state": state_material,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode()).hexdigest()
