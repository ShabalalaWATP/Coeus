"""Organisational teams, member profiles and team calendars.

Distinct from the advisory capability catalogue: these records hold people
and access, while the catalogue is static matchmaking data. The optional
``capability_team_id`` soft link lets the UI show live availability beside
a recommended capability team.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class TeamKind(StrEnum):
    RFA = "rfa"
    CM = "cm"
    JIOC = "jioc"
    QC = "qc"


class CalendarStatus(StrEnum):
    AVAILABLE = "available"
    ON_TASK = "on_task"
    LEAVE = "leave"
    COURSE = "course"
    DUTY = "duty"
    APPOINTMENT = "appointment"
    OTHER = "other"


# Statuses that mean the member is committed elsewhere (not leave, not
# ticket work): courses, duty travel, appointments and ad-hoc blocks.
OTHER_COMMITMENT_STATUSES = frozenset(
    {
        CalendarStatus.COURSE,
        CalendarStatus.DUTY,
        CalendarStatus.APPOINTMENT,
        CalendarStatus.OTHER,
    }
)


@dataclass(frozen=True)
class OrgTeam:
    team_id: UUID
    name: str
    kind: TeamKind
    manager_user_ids: tuple[UUID, ...] = ()
    member_user_ids: tuple[UUID, ...] = ()
    capability_team_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class UserProfile:
    user_id: UUID
    title: str = ""
    specialisms: tuple[str, ...] = ()
    bio: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class TeamCalendarEntry:
    entry_id: UUID
    team_id: UUID
    user_id: UUID
    # ISO calendar date the entry starts on, e.g. "2026-07-10".
    entry_date: str
    status: CalendarStatus
    note: str = ""
    # Inclusive ISO end date for block entries; "" means a single day.
    end_date: str = ""
    created_by_user_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def entry_end(entry: TeamCalendarEntry) -> str:
    """The inclusive last day an entry covers."""
    return entry.end_date or entry.entry_date


def entry_covers(entry: TeamCalendarEntry, day: str) -> bool:
    """Whether an entry covers an ISO date (lexicographic compare is safe)."""
    return entry.entry_date <= day <= entry_end(entry)


def team_member_ids(team: OrgTeam) -> frozenset[UUID]:
    """Everyone on the team: managers lead it and are members of it."""
    return frozenset(team.manager_user_ids) | frozenset(team.member_user_ids)
