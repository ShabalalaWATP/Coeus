"""Action-specific authority resolution for canonical management boards."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_task_board import (
    TeamBoardQuery,
    TeamBoardScope,
    TeamTaskBoardDenied,
    TeamTaskBoardIntegrityError,
)
from coeus.persistence.organisation_authority_validation import validate_lineage


@dataclass(frozen=True)
class BoardAuthority:
    detail_unit_ids: tuple[UUID, ...]
    aggregate_unit_ids: tuple[UUID, ...]


def resolve_board_authority(
    connection: Connection,
    actor_id: UUID,
    root_unit_id: UUID,
    query: TeamBoardQuery,
    effective_at: datetime,
) -> BoardAuthority:
    units = _scope_units(connection, root_unit_id, query.scope)
    grants = tuple(
        connection.execute(
            text(_GRANTS),
            {"actor_id": actor_id, "root_id": root_unit_id, "at": effective_at},
        ).mappings()
    )
    if len(grants) > 200:
        raise TeamTaskBoardIntegrityError("management board grant scope exceeds its bound")
    valid = tuple(row for row in grants if _valid(connection, row, actor_id, effective_at))
    root_task = _covered(connection, valid, root_unit_id, ManagementAction.TASK_VIEW)
    root_aggregate = _covered(
        connection, valid, root_unit_id, ManagementAction.ORGANISATION_VIEW_AGGREGATE
    )
    if not root_task and (query.scope is TeamBoardScope.DIRECT or not root_aggregate):
        raise TeamTaskBoardDenied
    requested = set(query.unit_ids)
    available = set(units)
    if requested and not requested.issubset(available):
        raise TeamTaskBoardDenied
    selected = tuple(unit_id for unit_id in units if not requested or unit_id in requested)
    detail = tuple(
        unit_id
        for unit_id in selected
        if _covered(connection, valid, unit_id, ManagementAction.TASK_VIEW)
    )
    aggregate = tuple(
        unit_id
        for unit_id in selected
        if unit_id not in detail
        and _covered(connection, valid, unit_id, ManagementAction.ORGANISATION_VIEW_AGGREGATE)
    )
    return BoardAuthority(detail, aggregate)


def _scope_units(
    connection: Connection, root_unit_id: UUID, scope: TeamBoardScope
) -> tuple[UUID, ...]:
    if scope is TeamBoardScope.DIRECT:
        return (root_unit_id,)
    values = tuple(
        UUID(str(value))
        for value in connection.execute(
            text(
                "SELECT closure.descendant_unit_id "
                "FROM organisation_unit_closure closure "
                "JOIN organisation_units unit "
                "ON unit.unit_id=closure.descendant_unit_id "
                "WHERE closure.ancestor_unit_id=:root AND unit.is_active "
                "ORDER BY closure.depth,closure.descendant_unit_id LIMIT 501"
            ),
            {"root": root_unit_id},
        ).scalars()
    )
    if len(values) > 500:
        raise TeamTaskBoardIntegrityError("management board descendant scope exceeds its bound")
    return values


def _valid(
    connection: Connection,
    row: RowMapping,
    actor_id: UUID,
    at: datetime,
) -> bool:
    try:
        validate_lineage(
            connection,
            UUID(str(row["grant_id"])),
            actor_id,
            UUID(str(row["root_unit_id"])),
            ManagementAction(str(row["action"])),
            at,
        )
    except OrganisationAuthorityDenied:
        return False
    return True


def _covered(
    connection: Connection,
    rows: tuple[RowMapping, ...],
    unit_id: UUID,
    action: ManagementAction,
) -> bool:
    return any(
        ManagementAction(str(row["action"])) is action
        and (
            UUID(str(row["root_unit_id"])) == unit_id
            or (
                bool(row["include_descendants"])
                and connection.execute(
                    text(
                        "SELECT 1 FROM organisation_unit_closure "
                        "WHERE ancestor_unit_id=:root AND descendant_unit_id=:unit LIMIT 1"
                    ),
                    {"root": row["root_unit_id"], "unit": unit_id},
                ).first()
                is not None
            )
        )
        for row in rows
    )


_GRANTS = """
SELECT grant_row.* FROM team_management_grants grant_row
WHERE grant_row.manager_user_id=:actor_id
  AND grant_row.action IN ('task:view','organisation:view_aggregate')
  AND grant_row.valid_from<=:at
  AND (grant_row.valid_until IS NULL OR :at<grant_row.valid_until)
  AND (grant_row.revoked_at IS NULL OR :at<grant_row.revoked_at)
  AND (
    grant_row.root_unit_id=:root_id OR
    EXISTS(SELECT 1 FROM organisation_unit_closure closure
           WHERE closure.ancestor_unit_id=grant_row.root_unit_id
             AND closure.descendant_unit_id=:root_id
             AND grant_row.include_descendants) OR
    EXISTS(SELECT 1 FROM organisation_unit_closure closure
           WHERE closure.ancestor_unit_id=:root_id
             AND closure.descendant_unit_id=grant_row.root_unit_id)
  )
ORDER BY grant_row.grant_id LIMIT 201
"""
