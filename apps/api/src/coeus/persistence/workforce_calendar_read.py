"""Read-only queries for canonical workforce calendars."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from coeus.domain.workforce_calendar import CalendarEvent
from coeus.persistence import workforce_calendar_sql as sql
from coeus.persistence.workforce_calendar_rows import decode_event


def get_event(engine: Engine, event_id: UUID) -> CalendarEvent | None:
    with engine.begin() as connection:
        row = connection.execute(text(sql.GET_EVENT), {"event_id": event_id}).mappings().first()
        return None if row is None else decode_event(row)


def list_owner_events(
    engine: Engine,
    owner_user_id: UUID,
    window_start: datetime,
    window_end: datetime,
) -> tuple[CalendarEvent, ...]:
    with engine.begin() as connection:
        rows = connection.execute(
            text(sql.LIST_OWNER),
            {
                "owner_user_id": owner_user_id,
                "window_start": window_start,
                "window_end": window_end,
                "window_start_date": window_start.date(),
                "window_end_date": window_end.date(),
                "limit": 1000,
            },
        ).mappings()
        return tuple(decode_event(row) for row in rows)
