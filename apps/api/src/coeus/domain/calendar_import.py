"""Safe, preview-bound import contracts for the legacy team calendar."""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.teams import CalendarStatus, TeamCalendarEntry
from coeus.domain.workforce_calendar import AvailabilityEffect, CalendarActivity


class CalendarImportConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class LegacyCalendarCandidate:
    legacy_entry_id: UUID
    event_id: UUID
    scope_id: UUID
    history_id: UUID
    calendar_command_id: UUID
    team_id: UUID
    owner_user_id: UUID
    creator_user_id: UUID
    all_day_start: date
    all_day_end: date
    activity: CalendarActivity
    availability: AvailabilityEffect
    note: str
    created_at: datetime


@dataclass(frozen=True)
class CalendarImportFinding:
    code: str
    legacy_entry_id: UUID
    blocking: bool = True


@dataclass(frozen=True)
class CalendarImportInspection:
    state_digest: str
    importable: tuple[LegacyCalendarCandidate, ...]
    existing_count: int
    findings: tuple[CalendarImportFinding, ...]


@dataclass(frozen=True)
class CalendarImportPreview:
    preview_hash: str
    source_digest: str
    state_digest: str
    source_count: int
    importable_count: int
    existing_count: int
    findings: tuple[CalendarImportFinding, ...]


@dataclass(frozen=True)
class CalendarImportCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    preview_hash: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.idempotency_key) <= 128:
            raise ValueError("calendar import idempotency key is invalid")
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class CalendarImportResult:
    command_id: UUID
    imported_count: int
    existing_count: int
    replayed: bool


def candidate_from_legacy(entry: TeamCalendarEntry) -> LegacyCalendarCandidate:
    start = date.fromisoformat(entry.entry_date)
    inclusive_end = date.fromisoformat(entry.end_date) if entry.end_date else start
    if inclusive_end < start:
        raise ValueError("legacy calendar end date precedes its start")
    if entry.created_at.tzinfo is None or entry.created_at.utcoffset() is None:
        raise ValueError("legacy calendar created_at must be timezone-aware")
    if len(entry.note) > 280:
        raise ValueError("legacy calendar note exceeds the canonical limit")
    activity, availability = _STATUS_MAP[entry.status]
    key = str(entry.entry_id)
    return LegacyCalendarCandidate(
        entry.entry_id,
        uuid5(NAMESPACE_URL, f"coeus:legacy-calendar-event:v1:{key}"),
        uuid5(NAMESPACE_URL, f"coeus:legacy-calendar-scope:v1:{key}"),
        uuid5(NAMESPACE_URL, f"coeus:legacy-calendar-history:v1:{key}"),
        uuid5(NAMESPACE_URL, f"coeus:legacy-calendar-command:v1:{key}"),
        entry.team_id,
        entry.user_id,
        entry.created_by_user_id or entry.user_id,
        start,
        inclusive_end + timedelta(days=1),
        activity,
        availability,
        entry.note,
        entry.created_at.astimezone(UTC),
    )


def calendar_import_source_digest(entries: tuple[TeamCalendarEntry, ...]) -> str:
    payload = [
        {
            "created_at": entry.created_at.isoformat(),
            "created_by": str(entry.created_by_user_id) if entry.created_by_user_id else None,
            "end": entry.end_date,
            "entry": str(entry.entry_id),
            "note_hash": sha256(entry.note.encode()).hexdigest(),
            "owner": str(entry.user_id),
            "start": entry.entry_date,
            "status": entry.status.value,
            "team": str(entry.team_id),
        }
        for entry in sorted(entries, key=lambda item: str(item.entry_id))
    ]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def calendar_import_preview_hash(actor: UUID, source_digest: str, state_digest: str) -> str:
    _digest(source_digest, "source_digest")
    _digest(state_digest, "state_digest")
    value = f"calendar-import-v1:{actor}:{source_digest}:{state_digest}"
    return sha256(value.encode()).hexdigest()


def _digest(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


_STATUS_MAP = {
    CalendarStatus.AVAILABLE: (CalendarActivity.OTHER, AvailabilityEffect.AVAILABLE),
    CalendarStatus.ON_TASK: (CalendarActivity.TASK, AvailabilityEffect.UNAVAILABLE),
    CalendarStatus.LEAVE: (CalendarActivity.LEAVE, AvailabilityEffect.UNAVAILABLE),
    CalendarStatus.COURSE: (CalendarActivity.TRAINING, AvailabilityEffect.UNAVAILABLE),
    CalendarStatus.DUTY: (CalendarActivity.DUTY, AvailabilityEffect.UNAVAILABLE),
    CalendarStatus.APPOINTMENT: (
        CalendarActivity.APPOINTMENT,
        AvailabilityEffect.UNAVAILABLE,
    ),
    CalendarStatus.OTHER: (CalendarActivity.OTHER, AvailabilityEffect.UNAVAILABLE),
}
