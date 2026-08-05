"""Encoding helpers for canonical calendar rows."""

import json
from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy.engine import RowMapping

from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarEventStatus,
    CalendarFrequency,
    CalendarOccurrenceException,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)


def decode_event(row: RowMapping) -> CalendarEvent:
    return CalendarEvent(
        UUID(str(row["event_id"])),
        UUID(str(row["owner_user_id"])),
        CalendarEventSource(str(row["source"])),
        CalendarActivity(str(row["activity_category"])),
        CalendarTiming(
            str(row["time_zone"]),
            cast(datetime | None, row["starts_at"]),
            cast(datetime | None, row["ends_at"]),
            cast(date | None, row["all_day_start"]),
            cast(date | None, row["all_day_end"]),
        ),
        AvailabilityEffect(str(row["availability_effect"])),
        CalendarPrivacy(str(row["privacy_level"])),
        UUID(str(row["created_by_user_id"])),
        str(row["note"]),
        decode_recurrence(row["recurrence_rule"]),
        None if row["manager_scope_unit_id"] is None else UUID(str(row["manager_scope_unit_id"])),
        CalendarEventStatus(str(row["status"])),
        int(str(row["version"])),
        cast(datetime, row["created_at"]),
        cast(datetime, row["updated_at"]),
        cast(datetime | None, row["cancelled_at"]),
        decode_exceptions(row.get("exception_rows")),
        None if row.get("deduplication_key") is None else str(row["deduplication_key"]),
    )


def event_params(event: CalendarEvent) -> dict[str, object]:
    recurrence = event.recurrence
    return {
        "event_id": event.event_id,
        "owner_user_id": event.owner_user_id,
        "source": event.source.value,
        "activity_category": event.activity.value,
        "starts_at": event.timing.starts_at,
        "ends_at": event.timing.ends_at,
        "all_day_start": event.timing.all_day_start,
        "all_day_end": event.timing.all_day_end,
        "time_zone": event.timing.time_zone,
        "availability_effect": event.availability.value,
        "privacy_level": event.privacy.value,
        "note": event.note,
        "recurrence_rule": None
        if recurrence is None
        else json.dumps(
            {
                "frequency": recurrence.frequency.value,
                "interval": recurrence.interval,
                "until": recurrence.until.isoformat(),
                "weekdays": list(recurrence.weekdays),
            },
            sort_keys=True,
        ),
        "status": event.status.value,
        "manager_scope_unit_id": event.manager_scope_unit_id,
        "created_by_user_id": event.created_by_user_id,
        "deduplication_key": event.deduplication_key,
    }


def event_snapshot(event: CalendarEvent) -> str:
    """Serialise a bounded event version for protected immutable history."""
    values = event_params(event)
    values.update(
        {
            "version": event.version,
            "created_at": event.created_at,
            "updated_at": event.updated_at,
            "cancelled_at": event.cancelled_at,
            "exceptions": [
                {
                    "occurrence_key": item.occurrence_key,
                    "cancelled": item.cancelled,
                    "timing": None if item.timing is None else vars(item.timing),
                    "activity": item.activity,
                    "availability": item.availability,
                    "privacy": item.privacy,
                    "note": item.note,
                }
                for item in event.exceptions
            ],
        }
    )
    return json.dumps(values, default=str, sort_keys=True, separators=(",", ":"))


def decode_recurrence(value: object) -> CalendarRecurrence | None:
    if value is None:
        return None
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("stored recurrence rule is invalid")
    return CalendarRecurrence(
        CalendarFrequency(str(parsed["frequency"])),
        int(str(parsed["interval"])),
        date.fromisoformat(str(parsed["until"])),
        tuple(int(str(item)) for item in parsed.get("weekdays", [])),
    )


def decode_exceptions(value: object) -> tuple[CalendarOccurrenceException, ...]:
    if value is None:
        return ()
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list) or len(parsed) > 500:
        raise ValueError("stored calendar exceptions are invalid")
    return tuple(_decode_exception(item) for item in parsed)


def _decode_exception(value: object) -> CalendarOccurrenceException:
    if not isinstance(value, dict):
        raise ValueError("stored calendar exception is invalid")
    action, replacement = value.get("action"), value.get("replacement")
    if action == "cancel" and replacement is None:
        return CalendarOccurrenceException(str(value["occurrence_key"]), True)
    if action != "change" or not isinstance(replacement, dict):
        raise ValueError("stored calendar exception action is invalid")
    timing = replacement.get("timing")
    if not isinstance(timing, dict):
        raise ValueError("stored calendar exception timing is invalid")
    return CalendarOccurrenceException(
        str(value["occurrence_key"]),
        False,
        CalendarTiming(
            str(timing["time_zone"]),
            _datetime(timing.get("starts_at")),
            _datetime(timing.get("ends_at")),
            _date(timing.get("all_day_start")),
            _date(timing.get("all_day_end")),
        ),
        CalendarActivity(str(replacement["activity"])),
        AvailabilityEffect(str(replacement["availability"])),
        CalendarPrivacy(str(replacement["privacy"])),
        str(replacement["note"]),
    )


def _datetime(value: object) -> datetime | None:
    return None if value is None else datetime.fromisoformat(str(value))


def _date(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))
