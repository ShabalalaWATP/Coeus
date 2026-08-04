"""Unit coverage for preview-bound legacy-calendar imports."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.api.calendar_import_contracts import call_calendar_import
from coeus.core.errors import AppError
from coeus.domain.calendar_import import (
    CalendarImportCommand,
    CalendarImportConflict,
    CalendarImportFinding,
    CalendarImportInspection,
    CalendarImportResult,
    calendar_import_source_digest,
    candidate_from_legacy,
)
from coeus.domain.teams import CalendarStatus, OrgTeam, TeamCalendarEntry, TeamKind
from coeus.services.calendar_import import CalendarImportService

NOW = datetime(2026, 8, 4, 10, tzinfo=UTC)


def _team():
    return OrgTeam(uuid4(), "Synthetic Team", TeamKind.RFA)


def _entry(team_id=None, *, status=CalendarStatus.LEAVE):
    owner = uuid4()
    return TeamCalendarEntry(
        uuid4(),
        team_id or uuid4(),
        owner,
        "2026-08-10",
        status,
        "Sensitive synthetic appointment detail.",
        "2026-08-11",
        uuid4(),
        NOW,
    )


class _Source:
    def __init__(self, team, entries):  # type: ignore[no-untyped-def]
        self.team = team
        self.entries = entries

    def list_all_entries(self):  # type: ignore[no-untyped-def]
        return tuple(self.entries)


class _Store:
    def __init__(self):
        self.findings = ()
        self.replayed = None
        self.applied = None

    def inspect(self, candidates):  # type: ignore[no-untyped-def]
        return CalendarImportInspection("b" * 64, candidates, 0, self.findings)

    def replay(self, command):  # type: ignore[no-untyped-def]
        return self.replayed

    def apply(self, command, source_digest, candidates):  # type: ignore[no-untyped-def]
        self.applied = (command, source_digest, candidates)
        return CalendarImportResult(command.command_id, len(candidates), 0, False)


@pytest.mark.parametrize(
    ("status", "activity", "availability"),
    (
        (CalendarStatus.AVAILABLE, "other", "available"),
        (CalendarStatus.ON_TASK, "task", "unavailable"),
        (CalendarStatus.LEAVE, "leave", "unavailable"),
        (CalendarStatus.COURSE, "training", "unavailable"),
        (CalendarStatus.DUTY, "duty", "unavailable"),
        (CalendarStatus.APPOINTMENT, "appointment", "unavailable"),
        (CalendarStatus.OTHER, "other", "unavailable"),
    ),
)
def test_candidate_mapping_is_stable_and_end_exclusive(
    status: CalendarStatus, activity: str, availability: str
) -> None:
    entry = _entry(status=status)
    first = candidate_from_legacy(entry)
    second = candidate_from_legacy(entry)
    assert first == second
    assert first.event_id == second.event_id
    assert first.activity.value == activity
    assert first.availability.value == availability
    assert first.all_day_start.isoformat() == "2026-08-10"
    assert first.all_day_end.isoformat() == "2026-08-12"
    assert first.creator_user_id == entry.created_by_user_id


def test_candidate_defaults_creator_and_rejects_invalid_temporal_data() -> None:
    entry = _entry()
    candidate = candidate_from_legacy(replace(entry, created_by_user_id=None))
    assert candidate.creator_user_id == entry.user_id
    with pytest.raises(ValueError, match="precedes"):
        candidate_from_legacy(replace(entry, end_date="2026-08-09"))
    with pytest.raises(ValueError, match="timezone-aware"):
        candidate_from_legacy(replace(entry, created_at=NOW.replace(tzinfo=None)))
    with pytest.raises(ValueError, match="canonical limit"):
        candidate_from_legacy(replace(entry, note="x" * 281))


def test_source_digest_detects_note_changes_without_exposing_note() -> None:
    entry = _entry()
    first = calendar_import_source_digest((entry,))
    second = calendar_import_source_digest((replace(entry, note="Changed secret"),))
    assert first != second
    assert "Sensitive" not in first


def test_preview_and_apply_are_bound_to_exact_source_and_actor() -> None:
    team = _team()
    source = _Source(team, [_entry(team.team_id)])
    store = _Store()
    service = CalendarImportService(source, store)
    actor = uuid4()
    preview = service.preview(actor)
    assert preview.source_count == preview.importable_count == 1
    command = CalendarImportCommand(uuid4(), "import-once", actor, preview.preview_hash)
    result = service.apply(command)
    assert result.imported_count == 1 and result.replayed is False
    assert store.applied is not None


def test_apply_replays_before_reading_source() -> None:
    team = _team()
    source = _Source(team, [])
    store = _Store()
    command = CalendarImportCommand(uuid4(), "replay", uuid4(), "a" * 64)
    store.replayed = CalendarImportResult(command.command_id, 2, 1, True)
    result = CalendarImportService(source, store).apply(command)
    assert result.replayed and result.imported_count == 2


def test_stale_and_blocking_previews_fail_closed() -> None:
    team = _team()
    source = _Source(team, [_entry(team.team_id)])
    store = _Store()
    service = CalendarImportService(source, store)
    with pytest.raises(CalendarImportConflict, match="stale"):
        service.apply(CalendarImportCommand(uuid4(), "stale", uuid4(), "a" * 64))
    actor = uuid4()
    preview = service.preview(actor)
    store.findings = (
        CalendarImportFinding("canonical_event_collision", source.entries[0].entry_id),
    )
    blocked = service.preview(actor)
    assert blocked.preview_hash == preview.preview_hash
    with pytest.raises(CalendarImportConflict, match="blocking"):
        service.apply(CalendarImportCommand(uuid4(), "blocked", actor, blocked.preview_hash))


def test_invalid_duplicate_and_oversized_sources_are_bounded() -> None:
    team = _team()
    invalid = replace(_entry(team.team_id), entry_date="not-a-date")
    service = CalendarImportService(_Source(team, [invalid]), _Store())
    preview = service.preview(uuid4())
    assert preview.findings[0].code == "invalid_legacy_entry"
    duplicate = _entry(team.team_id)
    with pytest.raises(CalendarImportConflict, match="duplicate"):
        CalendarImportService(_Source(team, [duplicate, duplicate]), _Store()).preview(uuid4())
    entries = [replace(_entry(team.team_id), entry_id=uuid4()) for _ in range(501)]
    with pytest.raises(CalendarImportConflict, match="500"):
        CalendarImportService(_Source(team, entries), _Store()).preview(uuid4())


def test_command_and_http_contract_validation_is_bounded() -> None:
    with pytest.raises(ValueError, match="idempotency"):
        CalendarImportCommand(uuid4(), "", uuid4(), "a" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        CalendarImportCommand(uuid4(), "valid", uuid4(), "not-a-digest")
    with pytest.raises(AppError) as captured:
        call_calendar_import(lambda: (_ for _ in ()).throw(ValueError("invalid source")))
    assert captured.value.status_code == 422


def test_apply_detects_source_change_after_preview() -> None:
    team = _team()
    first = _entry(team.team_id)
    second = replace(first, note="Changed after preview")

    class ChangingSource:
        calls = 0

        def list_all_entries(self):  # type: ignore[no-untyped-def]
            self.calls += 1
            return (first,) if self.calls <= 2 else (second,)

    service = CalendarImportService(ChangingSource(), _Store())
    actor = uuid4()
    preview = service.preview(actor)
    with pytest.raises(CalendarImportConflict, match="changed before apply"):
        service.apply(CalendarImportCommand(uuid4(), "changed", actor, preview.preview_hash))
