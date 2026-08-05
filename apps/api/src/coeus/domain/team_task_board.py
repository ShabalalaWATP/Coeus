"""Privacy-minimised canonical team and management board projections."""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from coeus.domain.team_task_ownership import WorkflowLeg


class TeamBoardColumn(StrEnum):
    AWAITING_ASSIGNMENT = "awaiting_analyst_assignment"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    MANAGER_REVIEW = "manager_review"
    QC_REVIEW = "qc_review"
    REWORK = "rework"
    ON_HOLD = "on_hold"
    COMPLETED_RECENTLY = "completed_recently"


@dataclass(frozen=True)
class TeamTaskPackage:
    package_id: UUID
    title: str
    state: str
    accountable_user_id: UUID | None
    estimated_minutes: int | None
    remaining_minutes: int | None
    due_at: datetime | None
    priority: int | None
    version: int


@dataclass(frozen=True)
class TeamTaskCard:
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    reference: str
    title: str
    column: TeamBoardColumn
    priority: str
    target_date: date | None
    ticket_updated_at: datetime
    ticket_version: int
    ownership_version: int
    packages: tuple[TeamTaskPackage, ...] = ()
    unit_id: UUID | None = None
    unit_name: str | None = None


@dataclass(frozen=True)
class TeamBoardAggregate:
    """A child-team count that deliberately carries no ticket-level fields."""

    unit_id: UUID
    unit_name: str
    column: TeamBoardColumn
    count: int | None
    suppressed: bool


class TeamBoardScope(StrEnum):
    DIRECT = "direct"
    DESCENDANTS = "descendants"


@dataclass(frozen=True)
class TeamBoardQuery:
    scope: TeamBoardScope = TeamBoardScope.DIRECT
    include_completed: bool = False
    columns: tuple[TeamBoardColumn, ...] = ()
    unit_ids: tuple[UUID, ...] = ()
    priority: str | None = None
    due_from: date | None = None
    due_to: date | None = None
    completed_after: date | None = None
    cursor: str | None = None
    limit: int = 50

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 100:
            raise ValueError("limit must be between one and 100")
        if len(self.unit_ids) > 20:
            raise ValueError("at most 20 teams may be filtered")
        if self.due_from and self.due_to and self.due_from > self.due_to:
            raise ValueError("due_from cannot be after due_to")
        if self.priority is not None and not 1 <= len(self.priority) <= 40:
            raise ValueError("priority must contain between one and 40 characters")


@dataclass(frozen=True)
class TeamBoardCursor:
    unit_id: UUID
    target_date: date | None
    ticket_id: UUID
    workflow_leg: WorkflowLeg


@dataclass(frozen=True)
class TeamTaskBoard:
    unit_id: UUID
    cards: tuple[TeamTaskCard, ...]
    as_of: datetime
    truncated: bool
    next_cursor: str | None = None
    aggregates: tuple[TeamBoardAggregate, ...] = ()
    scope: TeamBoardScope = TeamBoardScope.DIRECT


class TeamTaskBoardDenied(RuntimeError):
    """The actor has no current direct task-view authority."""


class TeamTaskBoardIntegrityError(RuntimeError):
    """Canonical ownership and ticket state cannot be safely projected."""


def encode_board_cursor(cursor: TeamBoardCursor) -> str:
    payload = json.dumps(
        [
            str(cursor.unit_id),
            cursor.target_date.isoformat() if cursor.target_date else None,
            str(cursor.ticket_id),
            cursor.workflow_leg.value,
        ],
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_board_cursor(value: str | None) -> TeamBoardCursor | None:
    if value is None:
        return None
    if not 1 <= len(value) <= 512:
        raise ValueError("team-board cursor is invalid")
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(raw, list) or len(raw) != 4:
            raise ValueError
        return TeamBoardCursor(
            UUID(raw[0]),
            date.fromisoformat(raw[1]) if raw[1] else None,
            UUID(raw[2]),
            WorkflowLeg(raw[3]),
        )
    except (binascii.Error, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError("team-board cursor is invalid") from exc
