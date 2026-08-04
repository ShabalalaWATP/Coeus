"""Deterministic cross-source calendar occurrence deduplication."""

from datetime import UTC, datetime

from coeus.domain.workforce_calendar import (
    CalendarDeduplicationIntegrityError,
    CalendarEventSource,
    CalendarOccurrence,
)

_PRECEDENCE = {
    CalendarEventSource.TASK: 0,
    CalendarEventSource.MANAGER: 1,
    CalendarEventSource.TEAM: 2,
    CalendarEventSource.PERSONAL: 3,
    CalendarEventSource.EXTERNAL: 4,
    CalendarEventSource.LEGACY: 5,
}


def occurrence_identity(occurrence: CalendarOccurrence) -> tuple[object, ...]:
    """Return identity shared by the same commitment from different sources."""
    event = occurrence.event
    timing = event.timing
    explicit = event.deduplication_key
    semantic = (
        event.owner_user_id,
        timing.starts_at,
        timing.ends_at,
        timing.all_day_start,
        timing.all_day_end,
        timing.time_zone,
        event.activity,
        event.availability,
    )
    return (*semantic, explicit or "")


def deduplicate_occurrences(
    occurrences: tuple[CalendarOccurrence, ...],
) -> tuple[CalendarOccurrence, ...]:
    """Choose one deterministic representative while retaining provenance."""
    _reject_corrupt_legacy_collisions(occurrences)
    grouped: dict[tuple[object, ...], list[CalendarOccurrence]] = {}
    for occurrence in occurrences:
        grouped.setdefault(occurrence_identity(occurrence), []).append(occurrence)
    chosen: list[CalendarOccurrence] = []
    for values in grouped.values():
        ordered = sorted(
            values,
            key=lambda item: (
                _PRECEDENCE[item.event.source],
                str(item.series_event_id),
                item.occurrence_key,
            ),
        )
        winner = ordered[0]
        sources = tuple(dict.fromkeys(item.event.source for item in ordered))
        chosen.append(
            CalendarOccurrence(
                winner.series_event_id,
                winner.occurrence_key,
                winner.event,
                winner.series_timing,
                sources,
            )
        )
    return tuple(sorted(chosen, key=_sort_key))


def _reject_corrupt_legacy_collisions(occurrences: tuple[CalendarOccurrence, ...]) -> None:
    """Fail unknown when legacy rows claim one interval with conflicting effects."""
    legacy: dict[tuple[object, ...], set[tuple[object, ...]]] = {}
    for item in occurrences:
        event = item.event
        if event.source is not CalendarEventSource.LEGACY:
            continue
        timing = event.timing
        interval = (
            event.owner_user_id,
            timing.starts_at,
            timing.ends_at,
            timing.all_day_start,
            timing.all_day_end,
        )
        legacy.setdefault(interval, set()).add((event.activity, event.availability))
    if any(len(values) > 1 for values in legacy.values()):
        raise CalendarDeduplicationIntegrityError(
            "conflicting legacy calendar overlap cannot be resolved safely"
        )


def _sort_key(item: CalendarOccurrence) -> datetime:
    timing = item.event.timing
    if timing.starts_at is not None:
        start = timing.starts_at
    else:
        if timing.all_day_start is None:
            raise CalendarDeduplicationIntegrityError("calendar timing has no start")
        start = datetime.combine(timing.all_day_start, datetime.min.time(), UTC)
    return start
