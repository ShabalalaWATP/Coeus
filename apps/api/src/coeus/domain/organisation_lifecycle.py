"""Previewed organisation lifecycle command records."""

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation import OrganisationCategory
from coeus.domain.organisation_validation import optional_text, text_value


class OrganisationMutationOperation(StrEnum):
    CREATE = "create"
    EDIT = "edit"


class OrganisationMutationDenied(PermissionError):
    pass


class OrganisationMutationConflict(RuntimeError):
    pass


class OrganisationMutationIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class OrganisationMutationRequest:
    operation: OrganisationMutationOperation
    unit_id: UUID
    parent_unit_id: UUID | None
    expected_version: int
    name: str
    short_name: str
    category: OrganisationCategory
    time_zone: str
    description: str
    authorising_grant_id: UUID
    reason: str

    def __post_init__(self) -> None:
        text_value(self.name, "name", 120)
        text_value(self.short_name, "short_name", 32)
        text_value(self.time_zone, "time_zone", 64)
        optional_text(self.description, "description", 1_000)
        text_value(self.reason, "reason", 500)
        if self.expected_version < 1:
            raise ValueError("expected_version must be positive")
        if self.operation is OrganisationMutationOperation.CREATE and self.parent_unit_id is None:
            raise ValueError("create requires parent_unit_id")
        if self.operation is OrganisationMutationOperation.EDIT and self.parent_unit_id is not None:
            raise ValueError("edit cannot change parent_unit_id")
        if self.unit_id == self.parent_unit_id:
            raise ValueError("an organisation unit cannot parent itself")


@dataclass(frozen=True)
class OrganisationMutationPreview:
    operation: OrganisationMutationOperation
    unit_id: UUID
    scope_unit_id: UUID
    expected_version: int
    preview_hash: str
    affected_descendants: int = 0
    affected_memberships: int = 0
    affected_grants: int = 0
    affected_task_legs: int = 0


@dataclass(frozen=True)
class OrganisationMutationCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: OrganisationMutationRequest
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
class OrganisationMutationResult:
    unit_id: UUID
    version: int
    topology_revision_id: UUID | None
    replayed: bool = False


def mutation_hash(request: OrganisationMutationRequest, actor_user_id: UUID) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        **{
            key: item.value
            if isinstance(item, StrEnum)
            else str(item)
            if isinstance(item, UUID)
            else item
            for key, item in vars(request).items()
        },
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
