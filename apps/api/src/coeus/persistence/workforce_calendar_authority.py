"""Final transactional authority validation for canonical calendar writes."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.workforce_calendar import (
    CalendarEventSource,
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationDenied,
)
from coeus.persistence import workforce_calendar_sql as sql
from coeus.persistence.organisation_authority_validation import (
    lock_lineages,
    validate_lineage,
)


def validate_calendar_authority(
    connection: Connection, command: CalendarMutationCommand, occurred_at: datetime
) -> None:
    request = command.request
    event = request.event
    if event.source is CalendarEventSource.PERSONAL:
        if command.actor_user_id != event.owner_user_id or request.authorising_grant_id is not None:
            raise CalendarMutationDenied("personal events are owner-managed")
        return
    if event.source not in {CalendarEventSource.MANAGER, CalendarEventSource.TEAM} or (
        request.authorising_grant_id is None
    ):
        raise CalendarMutationDenied("this event source has a separate authority path")
    target_unit_id = event.manager_scope_unit_id
    if event.source is CalendarEventSource.MANAGER:
        memberships = tuple(
            connection.execute(
                text(sql.LOCK_HOME_MEMBERSHIP),
                {"owner_user_id": event.owner_user_id, "occurred_at": occurred_at},
            ).mappings()
        )
        if len(memberships) != 1 or UUID(str(memberships[0]["unit_id"])) != target_unit_id:
            raise CalendarMutationConflict("the subject has no matching current home unit")
    if target_unit_id is None:
        raise CalendarMutationConflict("the calendar scope is unavailable")
    if event.source is CalendarEventSource.TEAM:
        active = connection.execute(
            text(
                "SELECT 1 FROM organisation_units WHERE unit_id=:unit AND is_active=TRUE "
                "AND valid_from<=:now AND (valid_until IS NULL OR :now<valid_until) FOR UPDATE"
            ),
            {"unit": target_unit_id, "now": occurred_at},
        ).first()
        if active is None:
            raise CalendarMutationConflict("the team calendar scope is not active")
    try:
        lock_lineages(connection, (request.authorising_grant_id,))
        validate_lineage(
            connection,
            request.authorising_grant_id,
            command.actor_user_id,
            target_unit_id,
            ManagementAction.CALENDAR_MANAGE,
            occurred_at,
        )
    except OrganisationAuthorityDenied as error:
        raise CalendarMutationDenied("no effective calendar management grant") from error
