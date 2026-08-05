"""Subject response lifecycle for manager-created calendar commitments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from coeus.domain.organisation_validation import aware, text_value

if TYPE_CHECKING:
    from coeus.domain.workforce_calendar import CalendarEvent


class CommitmentResponseState(StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    DISPUTED = "disputed"


@dataclass(frozen=True)
class CalendarCommitment:
    event: CalendarEvent
    response_state: CommitmentResponseState
    response_version: int
    notified_at: datetime
    responded_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.event.source.value != "manager":
            raise ValueError("only manager events are subject commitments")
        if self.response_version < 1:
            raise ValueError("commitment response version must be positive")
        aware(self.notified_at, "notified_at")
        aware(self.responded_at, "responded_at")


@dataclass(frozen=True)
class CalendarCommitmentResponse:
    event_id: UUID
    subject_user_id: UUID
    state: CommitmentResponseState
    expected_version: int
    reason: str = ""

    def __post_init__(self) -> None:
        if self.state is CommitmentResponseState.PENDING:
            raise ValueError("a subject cannot submit a pending response")
        if self.expected_version < 1:
            raise ValueError("commitment response version must be positive")
        if self.state is CommitmentResponseState.DISPUTED:
            text_value(self.reason, "dispute reason", 500)
        elif self.reason:
            raise ValueError("acknowledgement does not accept a reason")
