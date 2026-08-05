"""Privacy-minimised canonical personal work projection."""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from coeus.domain.team_task_ownership import WorkflowLeg


class MyWorkColumn(StrEnum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    REWORK = "rework"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


@dataclass(frozen=True)
class MyWorkCard:
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    package_id: UUID
    reference: str
    ticket_title: str
    package_title: str
    column: MyWorkColumn
    priority: int | None
    target_date: date | None
    due_at: datetime | None
    blocked_code: str | None
    review_at: datetime | None
    ticket_version: int
    ownership_version: int
    package_version: int


@dataclass(frozen=True)
class MyWorkPage:
    cards: tuple[MyWorkCard, ...]
    as_of: datetime
    next_cursor: str | None


@dataclass(frozen=True)
class MyWorkCursor:
    sort_at: datetime
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    sort_order: int
    package_id: UUID


class MyWorkIntegrityError(RuntimeError):
    pass


def encode_cursor(cursor: MyWorkCursor) -> str:
    payload = json.dumps(
        [
            cursor.sort_at.isoformat(),
            str(cursor.ticket_id),
            cursor.workflow_leg.value,
            cursor.sort_order,
            str(cursor.package_id),
        ],
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str | None) -> MyWorkCursor | None:
    if value is None:
        return None
    if not 1 <= len(value) <= 512:
        raise ValueError("my-work cursor is invalid")
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(raw, list) or len(raw) != 5:
            raise ValueError
        cursor = MyWorkCursor(
            datetime.fromisoformat(raw[0]),
            UUID(raw[1]),
            WorkflowLeg(raw[2]),
            int(raw[3]),
            UUID(raw[4]),
        )
        if cursor.sort_at.tzinfo is None:
            raise ValueError
        if cursor.sort_order < 0:
            raise ValueError
        return cursor
    except (binascii.Error, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError("my-work cursor is invalid") from exc
