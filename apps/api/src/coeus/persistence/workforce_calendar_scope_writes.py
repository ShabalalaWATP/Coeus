"""Deterministic calendar scope projection writes."""

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.workforce_calendar import CalendarEvent, CalendarEventSource
from coeus.persistence import workforce_calendar_sql as sql


def insert_scopes(connection: Connection, event: CalendarEvent, occurred_at: datetime) -> None:
    scopes: list[tuple[str, UUID | None]] = [("owner_global", None)]
    if event.source is CalendarEventSource.MANAGER:
        scopes.append(("home_unit", event.manager_scope_unit_id))
    elif event.source is CalendarEventSource.TEAM:
        scopes.append(("team_participant", event.manager_scope_unit_id))
    for scope_type, unit_id in scopes:
        connection.execute(
            text(sql.INSERT_SCOPE),
            {
                "scope_id": uuid5(
                    NAMESPACE_URL, f"coeus:calendar-scope:{event.event_id}:{scope_type}"
                ),
                "event_id": event.event_id,
                "scope_type": scope_type,
                "owner_user_id": event.owner_user_id,
                "unit_id": unit_id,
                "occurred_at": occurred_at,
            },
        )
