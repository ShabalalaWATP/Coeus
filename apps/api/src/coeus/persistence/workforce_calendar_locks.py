"""Ordered advisory and row locks for calendar commands."""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.workforce_calendar import CalendarMutationCommand
from coeus.persistence import workforce_calendar_sql as sql


def lock_calendar_command(connection: Connection, command: CalendarMutationCommand) -> None:
    request = command.request
    event_ids = {request.event.event_id}
    if request.future_event_id is not None:
        event_ids.add(request.future_event_id)
    values = {
        *(f"calendar-event:{event_id}" for event_id in event_ids),
        f"calendar-owner:{request.event.owner_user_id}",
        f"calendar-command:{command.command_id}",
        f"calendar-idempotency:{command.actor_user_id}:{command.idempotency_key}",
    }
    if request.authorising_grant_id is not None:
        values.add(f"grant:{request.authorising_grant_id}")
    for value in sorted(values):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"), {"value": value}
        )
    for event_id in sorted(event_ids, key=str):
        connection.execute(text(sql.LOCK_EVENT), {"event_id": event_id}).first()
