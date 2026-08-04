"""Ports for bounded legacy-calendar import."""

from typing import Protocol

from coeus.domain.calendar_import import (
    CalendarImportCommand,
    CalendarImportInspection,
    CalendarImportResult,
    LegacyCalendarCandidate,
)
from coeus.domain.teams import TeamCalendarEntry


class LegacyCalendarSource(Protocol):
    def list_all_entries(self) -> tuple[TeamCalendarEntry, ...]: ...


class CalendarImportStore(Protocol):
    def inspect(
        self, candidates: tuple[LegacyCalendarCandidate, ...]
    ) -> CalendarImportInspection: ...

    def replay(self, command: CalendarImportCommand) -> CalendarImportResult | None: ...

    def apply(
        self,
        command: CalendarImportCommand,
        source_digest: str,
        candidates: tuple[LegacyCalendarCandidate, ...],
    ) -> CalendarImportResult: ...
