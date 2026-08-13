"""Transactionally authorised PostgreSQL workspace discovery."""

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.organisation_workspace import OrganisationWorkspaceStore
from coeus.domain.organisation import ManagementAction, OrganisationUnit
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.organisation_workspace import (
    OrganisationWorkspace,
    OrganisationWorkspaceIntegrityError,
    OrganisationWorkspacePage,
    WorkspaceRelationship,
)
from coeus.persistence.organisation_authority_validation import (
    transaction_time,
    validate_lineage,
)
from coeus.persistence.organisation_rows import decode_unit

_ACTIONS = (
    ManagementAction.ORGANISATION_VIEW,
    ManagementAction.WORKSPACE_VIEW,
    ManagementAction.CALENDAR_VIEW_AVAILABILITY,
    ManagementAction.CALENDAR_VIEW_DETAIL,
    ManagementAction.CALENDAR_MANAGE,
    ManagementAction.TASK_VIEW,
    ManagementAction.TASK_ASSIGN,
    ManagementAction.WORKSPACE_CONFIGURE,
    ManagementAction.ROSTER_VIEW,
    ManagementAction.CAPABILITY_MANAGE,
    ManagementAction.WORKSPACE_EXPORT,
)

_HOME = """
SELECT u.*
FROM team_memberships m
JOIN organisation_units u ON u.unit_id = m.unit_id
WHERE m.user_id = :actor_id
  AND m.state = 'active'
  AND m.valid_from <= :effective_at
  AND (m.valid_until IS NULL OR :effective_at < m.valid_until)
  AND u.is_active = TRUE
  AND u.valid_from <= :effective_at
  AND (u.valid_until IS NULL OR :effective_at < u.valid_until)
LIMIT 2
"""

_GRANTS = """
SELECT g.*, u.unit_id AS workspace_unit_id, u.name, u.short_name, u.category,
       u.parent_unit_id, u.valid_from AS unit_valid_from,
       u.valid_until AS unit_valid_until, u.time_zone, u.description,
       u.is_active, u.version AS unit_version, u.provenance
FROM team_management_grants g
JOIN organisation_units u ON u.unit_id = g.root_unit_id
WHERE g.manager_user_id = :actor_id
  AND g.action = ANY(CAST(:actions AS text[]))
  AND g.valid_from <= :effective_at
  AND (g.valid_until IS NULL OR :effective_at < g.valid_until)
  AND (g.revoked_at IS NULL OR :effective_at < g.revoked_at)
  AND u.is_active = TRUE
  AND u.valid_from <= :effective_at
  AND (u.valid_until IS NULL OR :effective_at < u.valid_until)
ORDER BY u.name, g.grant_id
LIMIT 301
"""


class PostgresOrganisationWorkspaceStore(OrganisationWorkspaceStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_actor_workspaces(self, actor_user_id: UUID) -> OrganisationWorkspacePage:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            effective_at = transaction_time(connection)
            home_rows = tuple(
                connection.execute(
                    text(_HOME), {"actor_id": actor_user_id, "effective_at": effective_at}
                ).mappings()
            )
            grant_rows = tuple(
                connection.execute(
                    text(_GRANTS),
                    {
                        "actor_id": actor_user_id,
                        "effective_at": effective_at,
                        "actions": [action.value for action in _ACTIONS],
                    },
                ).mappings()
            )
            return _project(connection, actor_user_id, effective_at, home_rows, grant_rows)


def _project(
    connection: Connection,
    actor_user_id: UUID,
    effective_at: datetime,
    home_rows: tuple[RowMapping, ...],
    grant_rows: tuple[RowMapping, ...],
) -> OrganisationWorkspacePage:
    if len(home_rows) > 1:
        raise OrganisationWorkspaceIntegrityError("multiple effective home memberships")
    valid: dict[ManagementAction, list[RowMapping]] = defaultdict(list)
    truncated = len(grant_rows) > 300
    for row in grant_rows[:300]:
        action = ManagementAction(str(row["action"]))
        try:
            validate_lineage(
                connection,
                UUID(str(row["grant_id"])),
                actor_user_id,
                UUID(str(row["root_unit_id"])),
                action,
                effective_at,
            )
        except OrganisationAuthorityDenied:
            continue
        valid[action].append(row)

    workspaces: list[OrganisationWorkspace] = []
    if home_rows:
        unit = decode_unit(home_rows[0])
        managed_home_rows = [
            row
            for row in valid[ManagementAction.WORKSPACE_VIEW]
            if _row_covers(connection, row, unit.unit_id)
            and _covers_any(connection, valid[ManagementAction.ORGANISATION_VIEW], unit.unit_id)
        ]
        workspaces.append(
            _workspace(
                connection,
                unit,
                WorkspaceRelationship.HOME,
                bool(managed_home_rows),
                any(bool(row["include_descendants"]) for row in managed_home_rows)
                and _can_browse_descendants(
                    connection, valid[ManagementAction.ORGANISATION_VIEW], unit.unit_id
                ),
                valid,
            )
        )
    home_id = workspaces[0].unit.unit_id if workspaces else None
    managed: dict[UUID, tuple[RowMapping, bool]] = {}
    for row in valid[ManagementAction.WORKSPACE_VIEW]:
        unit_id = UUID(str(row["root_unit_id"]))
        if unit_id == home_id or not _covers_any(
            connection, valid[ManagementAction.ORGANISATION_VIEW], unit_id
        ):
            continue
        existing = managed.get(unit_id)
        include_descendants = bool(row["include_descendants"])
        managed[unit_id] = (
            row if existing is None else existing[0],
            include_descendants or (False if existing is None else existing[1]),
        )
    for row, include_descendants in managed.values():
        unit = decode_unit(_unit_row(row))
        workspaces.append(
            _workspace(
                connection,
                unit,
                WorkspaceRelationship.MANAGED,
                True,
                include_descendants
                and _can_browse_descendants(
                    connection, valid[ManagementAction.ORGANISATION_VIEW], unit.unit_id
                ),
                valid,
            )
        )
    return OrganisationWorkspacePage(
        tuple(workspaces[:100]), effective_at, truncated or len(workspaces) > 100
    )


def _workspace(
    connection: Connection,
    unit: OrganisationUnit,
    relationship: WorkspaceRelationship,
    managed: bool,
    include_descendants: bool,
    grants: dict[ManagementAction, list[RowMapping]],
) -> OrganisationWorkspace:
    configuration = _covering_grant(
        connection, grants[ManagementAction.WORKSPACE_CONFIGURE], unit.unit_id
    )
    export = _covering_grant(connection, grants[ManagementAction.WORKSPACE_EXPORT], unit.unit_id)
    roster_grant = _covers_any(connection, grants[ManagementAction.ROSTER_VIEW], unit.unit_id)
    # A member sees their own team's roster without a grant, because the home
    # workspace is built from an effective posting. Capability coverage stays
    # grant-only: it is management information, not "who am I working with".
    can_view_people = roster_grant or relationship is WorkspaceRelationship.HOME
    return OrganisationWorkspace(
        unit,
        relationship,
        managed,
        include_descendants,
        _covers_any(connection, grants[ManagementAction.CALENDAR_VIEW_AVAILABILITY], unit.unit_id),
        _covers_any(connection, grants[ManagementAction.CALENDAR_VIEW_DETAIL], unit.unit_id),
        _covers_any(connection, grants[ManagementAction.TASK_VIEW], unit.unit_id),
        _covering_grant_id(connection, grants[ManagementAction.TASK_ASSIGN], unit.unit_id),
        configuration[0] if configuration else None,
        configuration[1] if configuration else None,
        _covering_grant_id(connection, grants[ManagementAction.CALENDAR_MANAGE], unit.unit_id),
        can_view_people,
        roster_grant
        or _covers_any(connection, grants[ManagementAction.CAPABILITY_MANAGE], unit.unit_id),
        configuration is not None,
        export[0] if export else None,
        export[1] if export else None,
    )


def _covers_any(connection: Connection, rows: list[RowMapping], unit_id: UUID) -> bool:
    return any(_row_covers(connection, row, unit_id) for row in rows)


def _covering_grant_id(
    connection: Connection, rows: list[RowMapping], unit_id: UUID
) -> UUID | None:
    identifiers = sorted(
        UUID(str(row["grant_id"])) for row in rows if _row_covers(connection, row, unit_id)
    )
    return identifiers[0] if identifiers else None


def _covering_grant(
    connection: Connection, rows: list[RowMapping], unit_id: UUID
) -> tuple[UUID, int] | None:
    values = sorted(
        (
            UUID(str(row["grant_id"])),
            int(row["version"]),
        )
        for row in rows
        if _row_covers(connection, row, unit_id)
    )
    return values[0] if values else None


def _can_browse_descendants(connection: Connection, rows: list[RowMapping], unit_id: UUID) -> bool:
    return any(
        bool(row["include_descendants"]) and _row_covers(connection, row, unit_id) for row in rows
    )


def _row_covers(connection: Connection, row: RowMapping, unit_id: UUID) -> bool:
    return UUID(str(row["root_unit_id"])) == unit_id or (
        bool(row["include_descendants"])
        and connection.execute(
            text(
                "SELECT 1 FROM organisation_unit_closure "
                "WHERE ancestor_unit_id = :root AND descendant_unit_id = :target LIMIT 1"
            ),
            {"root": row["root_unit_id"], "target": unit_id},
        ).first()
        is not None
    )


def _unit_row(row: RowMapping) -> dict[str, object]:
    return {
        "unit_id": row["workspace_unit_id"],
        "name": row["name"],
        "short_name": row["short_name"],
        "category": row["category"],
        "parent_unit_id": row["parent_unit_id"],
        "valid_from": row["unit_valid_from"],
        "valid_until": row["unit_valid_until"],
        "time_zone": row["time_zone"],
        "description": row["description"],
        "is_active": row["is_active"],
        "version": row["unit_version"],
        "provenance": row["provenance"],
    }
