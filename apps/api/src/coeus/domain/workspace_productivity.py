"""Validated, privacy-minimised workspace productivity records."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.team_task_board import TeamBoardColumn, TeamBoardScope


class WorkspaceRecordDenied(PermissionError):
    pass


class WorkspaceRecordConflict(RuntimeError):
    pass


class WorkUpdateKind(StrEnum):
    ASSIGNMENT = "assignment"
    MENTION = "mention"
    DUE_SOON = "due_soon"
    BLOCKED_REVIEW = "blocked_review"
    RETURNED = "returned"
    TRANSFER_REQUEST = "transfer_request"
    CALENDAR_CONFLICT = "calendar_conflict"
    DELEGATION_EXPIRY = "delegation_expiry"


class DeliveryMode(StrEnum):
    IMMEDIATE = "immediate"
    DIGEST = "digest"


@dataclass(frozen=True)
class SavedBoardFilters:
    scope: TeamBoardScope = TeamBoardScope.DIRECT
    include_completed: bool = False
    columns: tuple[TeamBoardColumn, ...] = ()
    unit_ids: tuple[UUID, ...] = ()
    priority: str | None = None
    due_from: date | None = None
    due_to: date | None = None

    def __post_init__(self) -> None:
        if len(self.columns) > len(TeamBoardColumn) or len(set(self.columns)) != len(self.columns):
            raise ValueError("saved board statuses are invalid")
        if len(self.unit_ids) > 20 or len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("saved board team filters are invalid")
        if self.priority is not None:
            _text(self.priority, "priority", 40)
        if self.due_from and self.due_to and self.due_from > self.due_to:
            raise ValueError("due_from cannot be after due_to")


@dataclass(frozen=True)
class SavedBoardView:
    view_id: UUID
    owner_user_id: UUID
    unit_id: UUID
    name: str
    filters: SavedBoardFilters
    version: int
    updated_at: datetime

    def __post_init__(self) -> None:
        _text(self.name, "saved view name", 80)
        if self.version < 1:
            raise ValueError("saved view version must be positive")


@dataclass(frozen=True)
class PackageTemplate:
    template_id: UUID
    unit_id: UUID
    owner_user_id: UUID
    name: str
    package_titles: tuple[str, ...]
    estimated_minutes: int | None
    priority: int | None
    version: int
    updated_at: datetime

    def __post_init__(self) -> None:
        _text(self.name, "template name", 80)
        if not 1 <= len(self.package_titles) <= 20:
            raise ValueError("a template requires between one and 20 package titles")
        for title in self.package_titles:
            _text(title, "package title", 120)
        if self.estimated_minutes is not None and not 15 <= self.estimated_minutes <= 10080:
            raise ValueError("estimated minutes must be between 15 and 10080")
        if self.priority is not None and not 1 <= self.priority <= 5:
            raise ValueError("priority must be between one and five")


@dataclass(frozen=True)
class WorkUpdate:
    update_id: UUID
    recipient_user_id: UUID
    event_key: str
    kind: WorkUpdateKind
    unit_id: UUID
    object_type: str
    object_id: UUID
    occurred_at: datetime
    acknowledged_at: datetime | None = None


@dataclass(frozen=True)
class DeliveryPreferences:
    user_id: UUID
    mode: DeliveryMode
    due_reminders: bool
    version: int


@dataclass(frozen=True)
class WorkspaceStoreLink:
    link_id: UUID
    owner_user_id: UUID
    unit_id: UUID
    source_type: str
    source_id: UUID
    target_type: str
    target_id: UUID
    label: str
    version: int
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.source_type not in {"ticket", "work_package"}:
            raise ValueError("Store link source is invalid")
        if self.target_type not in {"project", "product"}:
            raise ValueError("Store link target is invalid")
        _text(self.label, "Store link label", 160)
        if self.version < 1:
            raise ValueError("Store link version must be positive")


@dataclass(frozen=True)
class ProductivityCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    operation: str
    payload: dict[str, object]

    def __post_init__(self) -> None:
        _text(self.idempotency_key, "idempotency key", 128)
        _text(self.operation, "operation", 50)

    @property
    def request_hash(self) -> str:
        encoded = json.dumps(
            self.payload,
            default=str,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return sha256(self.operation.encode() + b":" + encoded).hexdigest()


@dataclass(frozen=True)
class RecordPage[T]:
    items: tuple[T, ...]
    next_cursor: UUID | None


def _text(value: str, field: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"{field} must contain 1 to {maximum} trimmed characters")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field} cannot contain control characters")
