"""Transactional writes for one occurrence and future-series splits."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.calendar_occurrence_policy import split_series
from coeus.domain.workforce_calendar import (
    CalendarEvent,
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationOperation,
    CalendarMutationResult,
)
from coeus.persistence import workforce_calendar_sql as sql
from coeus.persistence.workforce_calendar_rows import decode_event, event_params, event_snapshot


def mutate_occurrence(
    connection: Connection, command: CalendarMutationCommand, occurred_at: datetime
) -> tuple[CalendarMutationResult, CalendarEvent]:
    request = command.request
    current = _current(connection, request.event.event_id)
    if request.operation is CalendarMutationOperation.UPDATE_FUTURE:
        return _split(connection, command, current, occurred_at)
    replacement = None
    action = "cancel"
    if request.operation is CalendarMutationOperation.UPDATE_OCCURRENCE:
        action = "change"
        replacement = _replacement(request.event)
    connection.execute(
        text(sql.UPSERT_EXCEPTION),
        {
            "exception_id": uuid5(
                NAMESPACE_URL,
                f"coeus:calendar-exception:{current.event_id}:{request.occurrence_key}",
            ),
            "event_id": current.event_id,
            "occurrence_key": request.occurrence_key,
            "action": action,
            "replacement": replacement,
            "actor_user_id": command.actor_user_id,
            "occurred_at": occurred_at,
        },
    )
    version = connection.execute(
        text(sql.BUMP_EVENT),
        {
            "event_id": current.event_id,
            "expected_version": request.expected_version,
            "occurred_at": occurred_at,
        },
    ).scalar_one_or_none()
    if version is None:
        raise CalendarMutationConflict("the calendar event identity or version is stale")
    stored = _current(connection, current.event_id)
    return CalendarMutationResult(stored.event_id, stored.version), stored


def _split(
    connection: Connection,
    command: CalendarMutationCommand,
    current: CalendarEvent,
    occurred_at: datetime,
) -> tuple[CalendarMutationResult, CalendarEvent]:
    parent, child = split_series(current, command.request)
    parent_version = connection.execute(
        text(sql.UPDATE_EVENT),
        {
            **event_params(parent),
            "expected_version": command.request.expected_version,
            "occurred_at": occurred_at,
        },
    ).scalar_one_or_none()
    if parent_version is None:
        raise CalendarMutationConflict("the calendar event identity or version is stale")
    child_version = connection.execute(
        text(sql.INSERT_EVENT), {**event_params(child), "occurred_at": occurred_at}
    ).scalar_one_or_none()
    if child_version is None:
        raise CalendarMutationConflict("the future calendar series could not be created")
    connection.execute(
        text(
            "DELETE FROM calendar_event_exceptions "
            "WHERE event_id=:parent_id AND occurrence_key>=:occurrence_key"
        ),
        {
            "parent_id": parent.event_id,
            "occurrence_key": command.request.occurrence_key,
        },
    )
    _copy_scopes(connection, parent.event_id, child.event_id, occurred_at)
    stored_parent, stored_child = (
        _current(connection, parent.event_id),
        _current(connection, child.event_id),
    )
    _write_child_history(connection, command, stored_child, occurred_at)
    return (
        CalendarMutationResult(
            stored_parent.event_id, stored_parent.version, future_event_id=stored_child.event_id
        ),
        stored_parent,
    )


def _copy_scopes(
    connection: Connection,
    parent_id: UUID,
    child_id: UUID,
    occurred_at: datetime,
) -> None:
    rows = connection.execute(
        text(
            "SELECT scope_type,subject_user_id,unit_id FROM calendar_event_scopes "
            "WHERE event_id=:id"
        ),
        {"id": parent_id},
    ).mappings()
    for row in rows:
        connection.execute(
            text(sql.INSERT_SCOPE),
            {
                "scope_id": uuid5(
                    NAMESPACE_URL, f"coeus:calendar-scope:{child_id}:{row['scope_type']}"
                ),
                "event_id": child_id,
                "scope_type": row["scope_type"],
                "owner_user_id": row["subject_user_id"],
                "unit_id": row["unit_id"],
                "occurred_at": occurred_at,
            },
        )


def _write_child_history(
    connection: Connection,
    command: CalendarMutationCommand,
    event: CalendarEvent,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(sql.INSERT_HISTORY),
        {
            "history_id": uuid5(
                NAMESPACE_URL, f"coeus:calendar-history:{event.event_id}:{event.version}"
            ),
            "event_id": event.event_id,
            "event_version": event.version,
            "snapshot": event_snapshot(event),
            "actor_user_id": command.actor_user_id,
            "occurred_at": occurred_at,
            "reason_hash": sha256(command.request.reason.encode()).hexdigest(),
        },
    )


def _current(connection: Connection, event_id: UUID) -> CalendarEvent:
    row = connection.execute(text(sql.GET_EVENT), {"event_id": event_id}).mappings().first()
    if row is None:
        raise CalendarMutationConflict("the calendar event does not exist")
    return decode_event(row)


def _replacement(event: CalendarEvent) -> str:
    return json.dumps(
        {
            "timing": vars(event.timing),
            "activity": event.activity.value,
            "availability": event.availability.value,
            "privacy": event.privacy.value,
            "note": event.note,
        },
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )
