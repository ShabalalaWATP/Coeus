"""Read-only PostgreSQL projection of canonical events through current memberships."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.workforce_calendar import (
    CalendarProjectionDenied,
    ScopedCalendarEvent,
)
from coeus.persistence import workforce_calendar_sql as sql
from coeus.persistence.organisation_authority_validation import (
    transaction_time,
    validate_lineage,
)
from coeus.persistence.workforce_calendar_rows import decode_event


def list_unit_events(
    engine: Engine,
    actor_user_id: UUID,
    authorising_grant_id: UUID,
    action: ManagementAction,
    root_unit_id: UUID,
    unit_ids: tuple[UUID, ...],
    window_start: datetime,
    window_end: datetime,
) -> tuple[ScopedCalendarEvent, ...]:
    if not unit_ids:
        return ()
    with engine.begin() as connection:
        effective_at = transaction_time(connection)
        try:
            leaf = validate_lineage(
                connection,
                authorising_grant_id,
                actor_user_id,
                root_unit_id,
                action,
                effective_at,
            )
        except OrganisationAuthorityDenied as error:
            raise CalendarProjectionDenied("calendar projection authority changed") from error
        if len(unit_ids) > 1 and not bool(leaf["include_descendants"]):
            raise CalendarProjectionDenied("descendant calendar authority changed")
        rows = connection.execute(
            text(sql.LIST_UNIT_EVENTS),
            {
                "unit_ids": list(unit_ids),
                "root_unit_id": root_unit_id,
                "effective_at": effective_at,
                "window_start": window_start,
                "window_end": window_end,
                "window_start_date": window_start.date(),
                "window_end_date": window_end.date(),
                "limit": 101,
            },
        ).mappings()
        return tuple(
            ScopedCalendarEvent(UUID(str(row["projection_unit_id"])), decode_event(row))
            for row in rows
        )
