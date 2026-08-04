"""Previewed, explicit-disposition organisation unit merge records."""

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation_validation import text_value


class OrganisationMergeDenied(PermissionError):
    pass


class OrganisationMergeConflict(RuntimeError):
    pass


class OrganisationMergeIdempotencyConflict(RuntimeError):
    pass


class MergeRecordKind(StrEnum):
    CHILD_UNIT = "child_unit"
    MEMBERSHIP = "membership"
    GRANT = "grant"
    DELIVERY_PROFILE = "delivery_profile"
    CAPABILITY = "capability"
    TASK = "task"
    PENDING_TRANSFER = "pending_transfer"


class MergeDispositionAction(StrEnum):
    MOVE = "move"
    END = "end"
    REVOKE = "revoke"
    CANCEL = "cancel"


_ACTIONS = {
    MergeRecordKind.CHILD_UNIT: frozenset({MergeDispositionAction.MOVE}),
    MergeRecordKind.MEMBERSHIP: frozenset(
        {MergeDispositionAction.MOVE, MergeDispositionAction.END}
    ),
    MergeRecordKind.GRANT: frozenset({MergeDispositionAction.REVOKE}),
    MergeRecordKind.DELIVERY_PROFILE: frozenset(
        {MergeDispositionAction.MOVE, MergeDispositionAction.END}
    ),
    MergeRecordKind.CAPABILITY: frozenset(
        {MergeDispositionAction.MOVE, MergeDispositionAction.END}
    ),
    MergeRecordKind.TASK: frozenset({MergeDispositionAction.MOVE, MergeDispositionAction.CANCEL}),
    MergeRecordKind.PENDING_TRANSFER: frozenset({MergeDispositionAction.CANCEL}),
}


@dataclass(frozen=True)
class MergeUnitVersion:
    unit_id: UUID
    expected_version: int

    def __post_init__(self) -> None:
        if self.expected_version < 1:
            raise ValueError("expected_version must be positive")


@dataclass(frozen=True)
class MergeUnitAuthority:
    unit_id: UUID
    grant_id: UUID


@dataclass(frozen=True)
class OrganisationMergeRequest:
    sources: tuple[MergeUnitVersion, ...]
    successor: MergeUnitVersion
    authorities: tuple[MergeUnitAuthority, ...]
    reason: str

    def __post_init__(self) -> None:
        source_ids = tuple(item.unit_id for item in self.sources)
        if len(source_ids) < 2 or len(source_ids) != len(set(source_ids)):
            raise ValueError("a merge requires at least two distinct source units")
        if self.successor.unit_id in source_ids:
            raise ValueError("the successor must be distinct from every source")
        authority_ids = tuple(item.unit_id for item in self.authorities)
        expected = {*source_ids, self.successor.unit_id}
        if len(authority_ids) != len(set(authority_ids)) or set(authority_ids) != expected:
            raise ValueError("authorities must map exactly one grant to every affected unit")
        text_value(self.reason, "reason", 500)


@dataclass(frozen=True)
class MergeAffectedRecord:
    kind: MergeRecordKind
    record_id: UUID
    source_unit_id: UUID
    version: int
    container_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("affected record version must be positive")


@dataclass(frozen=True)
class OrganisationMergeImpact:
    records: tuple[MergeAffectedRecord, ...]
    active_children: int
    newly_covering_grants: int
    maximum_result_depth: int
    reservations: int
    team_calendar_events: int
    saved_views: int
    successor_has_delivery_profile: bool
    state_digest: str

    def __post_init__(self) -> None:
        identities = tuple((item.kind, item.record_id) for item in self.records)
        if len(identities) != len(set(identities)):
            raise ValueError("affected records must be unique")
        for value in (
            self.active_children,
            self.newly_covering_grants,
            self.maximum_result_depth,
            self.reservations,
            self.team_calendar_events,
            self.saved_views,
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError("merge impact counts must be non-negative integers")
        _digest(self.state_digest, "state_digest")


@dataclass(frozen=True)
class MergeDisposition:
    kind: MergeRecordKind
    record_id: UUID
    expected_version: int
    action: MergeDispositionAction
    target_unit_id: UUID | None = None
    replacement_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.expected_version < 1:
            raise ValueError("expected_version must be positive")


@dataclass(frozen=True)
class OrganisationMergePlan:
    request: OrganisationMergeRequest
    dispositions: tuple[MergeDisposition, ...]


@dataclass(frozen=True)
class OrganisationMergePreview:
    plan: OrganisationMergePlan
    impact: OrganisationMergeImpact
    preview_hash: str

    def __post_init__(self) -> None:
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class OrganisationMergeCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    plan: OrganisationMergePlan
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
class OrganisationMergeResult:
    successor_unit_id: UUID
    successor_version: int
    source_versions: tuple[MergeUnitVersion, ...]
    replayed: bool = False

    def __post_init__(self) -> None:
        if self.successor_version < 1:
            raise ValueError("successor_version must be positive")


def merge_hash(
    plan: OrganisationMergePlan, actor_user_id: UUID, impact: OrganisationMergeImpact
) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "request": _serialise(plan.request),
        "dispositions": [_serialise(item) for item in plan.dispositions],
        "impact": _serialise(impact),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def validate_merge_dispositions(
    plan: OrganisationMergePlan, impact: OrganisationMergeImpact
) -> None:
    expected = {(item.kind, item.record_id): item for item in impact.records}
    supplied = {(item.kind, item.record_id): item for item in plan.dispositions}
    if len(supplied) != len(plan.dispositions) or supplied.keys() != expected.keys():
        raise OrganisationMergeConflict("every affected record requires exactly one disposition")
    profile_actions: dict[UUID, MergeDispositionAction] = {}
    moved_profiles = 0
    for identity, disposition in supplied.items():
        affected = expected[identity]
        if disposition.expected_version != affected.version:
            raise OrganisationMergeConflict("a disposition record version is stale")
        if disposition.action not in _ACTIONS[affected.kind]:
            raise OrganisationMergeConflict("a disposition action is invalid for its record kind")
        _validate_target(plan.request.successor.unit_id, affected.kind, disposition)
        if affected.kind is MergeRecordKind.DELIVERY_PROFILE:
            profile_actions[affected.record_id] = disposition.action
            moved_profiles += disposition.action is MergeDispositionAction.MOVE
    if moved_profiles > 1 or (moved_profiles and impact.successor_has_delivery_profile):
        raise OrganisationMergeConflict("delivery profiles would conflict at the successor")
    _validate_capabilities(impact, supplied, profile_actions)


def _validate_capabilities(
    impact: OrganisationMergeImpact,
    supplied: dict[tuple[MergeRecordKind, UUID], MergeDisposition],
    profile_actions: dict[UUID, MergeDispositionAction],
) -> None:
    for affected in impact.records:
        if affected.kind is not MergeRecordKind.CAPABILITY:
            continue
        if affected.container_id is None:
            raise OrganisationMergeConflict("a capability is missing its delivery profile")
        disposition = supplied[(affected.kind, affected.record_id)]
        if profile_actions.get(affected.container_id) is not disposition.action:
            raise OrganisationMergeConflict(
                "capability disposition must match its delivery profile"
            )


def _validate_target(
    successor_id: UUID, kind: MergeRecordKind, disposition: MergeDisposition
) -> None:
    if disposition.action is MergeDispositionAction.MOVE:
        if disposition.target_unit_id != successor_id:
            raise OrganisationMergeConflict("move dispositions must target the successor")
        if kind is MergeRecordKind.MEMBERSHIP and disposition.replacement_id is None:
            raise OrganisationMergeConflict("moved memberships require a replacement identity")
        if kind is not MergeRecordKind.MEMBERSHIP and disposition.replacement_id is not None:
            raise OrganisationMergeConflict("only moved memberships use replacement identities")
        return
    if disposition.target_unit_id is not None or disposition.replacement_id is not None:
        raise OrganisationMergeConflict("terminal dispositions cannot name a target or replacement")


def _serialise(value: object) -> object:
    if isinstance(value, UUID | StrEnum):
        return str(value)
    if isinstance(value, tuple):
        return [_serialise(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {key: _serialise(item) for key, item in vars(value).items()}
    return value


def _digest(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
