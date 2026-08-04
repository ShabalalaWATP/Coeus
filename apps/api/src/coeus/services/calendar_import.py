"""Application boundary for an explicit legacy-calendar import."""

from uuid import UUID

from coeus.application.ports.calendar_import import CalendarImportStore, LegacyCalendarSource
from coeus.domain.calendar_import import (
    CalendarImportCommand,
    CalendarImportConflict,
    CalendarImportFinding,
    CalendarImportPreview,
    CalendarImportResult,
    LegacyCalendarCandidate,
    calendar_import_preview_hash,
    calendar_import_source_digest,
    candidate_from_legacy,
)
from coeus.domain.teams import TeamCalendarEntry


class CalendarImportService:
    def __init__(self, source: LegacyCalendarSource, store: CalendarImportStore) -> None:
        self._source = source
        self._store = store

    def preview(self, actor_user_id: UUID) -> CalendarImportPreview:
        entries = self._entries()
        source_digest = calendar_import_source_digest(entries)
        candidates, invalid = _candidates(entries)
        inspection = self._store.inspect(candidates)
        findings = tuple(sorted((*invalid, *inspection.findings), key=_finding_key))
        return CalendarImportPreview(
            calendar_import_preview_hash(actor_user_id, source_digest, inspection.state_digest),
            source_digest,
            inspection.state_digest,
            len(entries),
            len(inspection.importable),
            inspection.existing_count,
            findings,
        )

    def apply(self, command: CalendarImportCommand) -> CalendarImportResult:
        replay = self._store.replay(command)
        if replay is not None:
            return replay
        preview = self.preview(command.actor_user_id)
        if preview.preview_hash != command.preview_hash:
            raise CalendarImportConflict("the legacy calendar import preview is stale")
        if any(finding.blocking for finding in preview.findings):
            raise CalendarImportConflict("the legacy calendar contains blocking findings")
        entries = self._entries()
        candidates, invalid = _candidates(entries)
        if invalid or calendar_import_source_digest(entries) != preview.source_digest:
            raise CalendarImportConflict("the legacy calendar changed before apply")
        return self._store.apply(command, preview.source_digest, candidates)

    def _entries(self) -> tuple[TeamCalendarEntry, ...]:
        values = list(self._source.list_all_entries())
        if len(values) > 500:
            raise CalendarImportConflict("the legacy calendar import exceeds 500 entries")
        if len({item.entry_id for item in values}) != len(values):
            raise CalendarImportConflict("the legacy calendar contains duplicate entry identities")
        return tuple(sorted(values, key=lambda item: str(item.entry_id)))


def _candidates(
    entries: tuple[TeamCalendarEntry, ...],
) -> tuple[tuple[LegacyCalendarCandidate, ...], tuple[CalendarImportFinding, ...]]:
    values: list[LegacyCalendarCandidate] = []
    findings: list[CalendarImportFinding] = []
    for entry in entries:
        try:
            values.append(candidate_from_legacy(entry))
        except (KeyError, OverflowError, ValueError):
            findings.append(CalendarImportFinding("invalid_legacy_entry", entry.entry_id))
    return tuple(values), tuple(findings)


def _finding_key(finding: CalendarImportFinding) -> tuple[str, str]:
    return finding.code, str(finding.legacy_entry_id)
