"""Previewed, explicit-mapping organisation split records."""

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation import OrganisationCategory
from coeus.domain.organisation_merge import (
    MergeAffectedRecord,
    MergeDisposition,
    MergeDispositionAction,
    MergeRecordKind,
    MergeUnitVersion,
)
from coeus.domain.organisation_validation import optional_text, text_value


class OrganisationSplitDenied(PermissionError):
    pass


class OrganisationSplitConflict(RuntimeError):
    pass


class OrganisationSplitIdempotencyConflict(RuntimeError):
    pass


_SPLIT_ACTIONS = {
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
class SplitSuccessor:
    unit_id: UUID
    name: str
    short_name: str
    category: OrganisationCategory
    time_zone: str
    description: str = ""

    def __post_init__(self) -> None:
        text_value(self.name, "name", 120)
        text_value(self.short_name, "short_name", 32)
        text_value(self.time_zone, "time_zone", 64)
        optional_text(self.description, "description", 1_000)


@dataclass(frozen=True)
class OrganisationSplitRequest:
    source: MergeUnitVersion
    parent: MergeUnitVersion
    successors: tuple[SplitSuccessor, ...]
    source_authorising_grant_id: UUID
    parent_authorising_grant_id: UUID
    reason: str

    def __post_init__(self) -> None:
        ids = tuple(item.unit_id for item in self.successors)
        if len(ids) < 2 or len(ids) != len(set(ids)):
            raise ValueError("a split requires at least two distinct successors")
        if self.source.unit_id == self.parent.unit_id or self.source.unit_id in ids:
            raise ValueError("source, parent and successor identities must be distinct")
        if self.parent.unit_id in ids:
            raise ValueError("a successor cannot replace the source parent")
        names = tuple(item.name.casefold() for item in self.successors)
        short_names = tuple(item.short_name.casefold() for item in self.successors)
        if len(names) != len(set(names)) or len(short_names) != len(set(short_names)):
            raise ValueError("successor names and short names must be unique")
        text_value(self.reason, "reason", 500)


@dataclass(frozen=True)
class OrganisationSplitImpact:
    records: tuple[MergeAffectedRecord, ...]
    reservations: int
    team_calendar_events: int
    saved_views: int
    state_digest: str

    def __post_init__(self) -> None:
        identities = tuple((item.kind, item.record_id) for item in self.records)
        if len(identities) != len(set(identities)):
            raise ValueError("affected records must be unique")
        if any(
            not isinstance(value, int) or value < 0
            for value in (self.reservations, self.team_calendar_events, self.saved_views)
        ):
            raise ValueError("split impact counts must be non-negative integers")
        _digest(self.state_digest, "state_digest")


@dataclass(frozen=True)
class OrganisationSplitPlan:
    request: OrganisationSplitRequest
    dispositions: tuple[MergeDisposition, ...]


@dataclass(frozen=True)
class OrganisationSplitPreview:
    plan: OrganisationSplitPlan
    impact: OrganisationSplitImpact
    preview_hash: str

    def __post_init__(self) -> None:
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class OrganisationSplitCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    plan: OrganisationSplitPlan
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
class OrganisationSplitResult:
    source: MergeUnitVersion
    parent: MergeUnitVersion
    successors: tuple[MergeUnitVersion, ...]
    replayed: bool = False


def split_hash(
    plan: OrganisationSplitPlan, actor_user_id: UUID, impact: OrganisationSplitImpact
) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "request": _serialise(plan.request),
        "dispositions": [_serialise(item) for item in plan.dispositions],
        "impact": _serialise(impact),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def validate_split_dispositions(
    plan: OrganisationSplitPlan, impact: OrganisationSplitImpact
) -> None:
    expected = {(item.kind, item.record_id): item for item in impact.records}
    supplied = {(item.kind, item.record_id): item for item in plan.dispositions}
    if len(supplied) != len(plan.dispositions) or supplied.keys() != expected.keys():
        raise OrganisationSplitConflict("every affected record requires exactly one disposition")
    successors = {item.unit_id: item for item in plan.request.successors}
    profile_dispositions: dict[UUID, MergeDisposition] = {}
    for identity, disposition in supplied.items():
        affected = expected[identity]
        if disposition.expected_version != affected.version:
            raise OrganisationSplitConflict("a disposition record version is stale")
        _validate_action(affected.kind, disposition, successors)
        if affected.kind is MergeRecordKind.DELIVERY_PROFILE:
            profile_dispositions[affected.record_id] = disposition
    _validate_capabilities(impact, supplied, profile_dispositions)


def _validate_action(
    kind: MergeRecordKind,
    disposition: MergeDisposition,
    successors: dict[UUID, SplitSuccessor],
) -> None:
    if disposition.action not in _SPLIT_ACTIONS[kind]:
        raise OrganisationSplitConflict("a split disposition has an invalid action")
    if disposition.action is MergeDispositionAction.MOVE:
        if disposition.target_unit_id not in successors:
            raise OrganisationSplitConflict("move dispositions must target a successor")
        delivery_records = {
            MergeRecordKind.MEMBERSHIP,
            MergeRecordKind.DELIVERY_PROFILE,
            MergeRecordKind.CAPABILITY,
            MergeRecordKind.TASK,
        }
        target = successors[disposition.target_unit_id]
        if kind in delivery_records and target.category is not OrganisationCategory.DELIVERY_TEAM:
            raise OrganisationSplitConflict("delivery records must target a delivery team")
        if kind is MergeRecordKind.MEMBERSHIP and disposition.replacement_id is None:
            raise OrganisationSplitConflict("moved memberships require a replacement identity")
        if kind is not MergeRecordKind.MEMBERSHIP and disposition.replacement_id is not None:
            raise OrganisationSplitConflict("only moved memberships use replacement identities")
    elif disposition.target_unit_id is not None or disposition.replacement_id is not None:
        raise OrganisationSplitConflict("terminal dispositions cannot name target records")


def _validate_capabilities(
    impact: OrganisationSplitImpact,
    supplied: dict[tuple[MergeRecordKind, UUID], MergeDisposition],
    profiles: dict[UUID, MergeDisposition],
) -> None:
    for affected in impact.records:
        if affected.kind is not MergeRecordKind.CAPABILITY:
            continue
        if affected.container_id is None or affected.container_id not in profiles:
            raise OrganisationSplitConflict("a capability is missing its delivery profile")
        capability = supplied[(affected.kind, affected.record_id)]
        profile = profiles[affected.container_id]
        if (capability.action, capability.target_unit_id) != (
            profile.action,
            profile.target_unit_id,
        ):
            raise OrganisationSplitConflict("capability mapping must follow its delivery profile")


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
