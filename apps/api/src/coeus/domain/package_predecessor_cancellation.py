"""Explicit dispositions for cancelling a package with dependants."""

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID


class DependantDispositionAction(StrEnum):
    CANCEL = "cancel"
    UNLINK = "unlink"
    REPLACE = "replace"


@dataclass(frozen=True)
class DependantDisposition:
    dependant_package_id: UUID
    expected_version: int
    action: DependantDispositionAction
    replacement_package_id: UUID | None = None
    expected_replacement_version: int | None = None

    def __post_init__(self) -> None:
        if self.expected_version < 1:
            raise ValueError("dependant package version must be positive")
        replacement = self.replacement_package_id is not None
        if replacement != (self.expected_replacement_version is not None):
            raise ValueError("replacement identity and version must be supplied together")
        if (self.action is DependantDispositionAction.REPLACE) != replacement:
            raise ValueError("only replacement disposition may identify a replacement")
        if self.expected_replacement_version is not None and self.expected_replacement_version < 1:
            raise ValueError("replacement package version must be positive")


@dataclass(frozen=True)
class PredecessorCancellationRequest:
    unit_id: UUID
    package_id: UUID
    expected_package_version: int
    expected_ownership_version: int
    authorising_grant_id: UUID
    expected_grant_version: int
    dispositions: tuple[DependantDisposition, ...]

    def __post_init__(self) -> None:
        if (
            min(
                self.expected_package_version,
                self.expected_ownership_version,
                self.expected_grant_version,
            )
            < 1
        ):
            raise ValueError("predecessor cancellation evidence versions must be positive")
        identities = [item.dependant_package_id for item in self.dispositions]
        if len(identities) != len(set(identities)) or len(identities) > 128:
            raise ValueError("dependant dispositions must be unique and bounded")


@dataclass(frozen=True)
class PredecessorCancellationPreview:
    preview_hash: str
    package_id: UUID
    package_version: int
    dependant_count: int
    planned_package_version: int


@dataclass(frozen=True)
class CancelPredecessorCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: PredecessorCancellationRequest
    preview_hash: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.idempotency_key) <= 128 or len(self.preview_hash) != 64:
            raise ValueError("predecessor cancellation command identity is invalid")


@dataclass(frozen=True)
class PredecessorCancellationResult:
    package_id: UUID
    package_version: int
    cancelled_dependants: int
    unlinked_dependants: int
    replaced_dependants: int
    replayed: bool


class PredecessorCancellationDenied(PermissionError):
    pass


class PredecessorCancellationConflict(ValueError):
    pass


def cancellation_hash(actor_user_id: UUID, request: PredecessorCancellationRequest) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "unit_id": str(request.unit_id),
        "package_id": str(request.package_id),
        "expected_package_version": request.expected_package_version,
        "expected_ownership_version": request.expected_ownership_version,
        "authorising_grant_id": str(request.authorising_grant_id),
        "expected_grant_version": request.expected_grant_version,
        "dispositions": [
            {
                "dependant_package_id": str(item.dependant_package_id),
                "expected_version": item.expected_version,
                "action": item.action.value,
                "replacement_package_id": (
                    str(item.replacement_package_id) if item.replacement_package_id else None
                ),
                "expected_replacement_version": item.expected_replacement_version,
            }
            for item in sorted(
                request.dispositions, key=lambda value: str(value.dependant_package_id)
            )
        ],
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
