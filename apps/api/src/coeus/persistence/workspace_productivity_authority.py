"""Current account and object-authority checks for workspace records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.workspace_productivity import WorkspaceRecordDenied
from coeus.persistence.organisation_authority_validation import validate_lineage


def require_active_actor(connection: Connection, actor: UUID, *, lock: bool = False) -> None:
    query = _ACTIVE_ACCOUNT_LOCKED if lock else _ACTIVE_ACCOUNT
    row = (
        connection.execute(
            text(query),
            {"actor": actor},
        )
        .mappings()
        .first()
    )
    if row is None or not bool(row["is_active"]):
        raise WorkspaceRecordDenied


_ACTIVE_ACCOUNT = "SELECT is_active FROM identity_account_projection WHERE user_id=:actor"
_ACTIVE_ACCOUNT_LOCKED = (
    "SELECT is_active FROM identity_account_projection WHERE user_id=:actor FOR UPDATE"
)


def require_action(
    connection: Connection,
    actor: UUID,
    unit_id: UUID,
    action: ManagementAction,
    at: datetime,
    *,
    grant_id: UUID | None = None,
    expected_version: int | None = None,
) -> UUID:
    rows = tuple(
        connection.execute(
            text(
                "SELECT grant_id,version,root_unit_id FROM team_management_grants "
                "WHERE manager_user_id=:actor AND action=:action "
                "AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until) "
                "AND (revoked_at IS NULL OR :at<revoked_at) "
                "AND (CAST(:grant_id AS uuid) IS NULL OR grant_id=CAST(:grant_id AS uuid)) "
                "ORDER BY grant_id LIMIT 201"
            ),
            {
                "actor": actor,
                "action": action.value,
                "at": at,
                "grant_id": grant_id,
            },
        ).mappings()
    )
    if len(rows) > 200:
        raise WorkspaceRecordDenied
    for row in rows:
        if expected_version is not None and int(row["version"]) != expected_version:
            continue
        candidate = UUID(str(row["grant_id"]))
        try:
            validate_lineage(connection, candidate, actor, unit_id, action, at)
        except OrganisationAuthorityDenied:
            continue
        return candidate
    raise WorkspaceRecordDenied


def require_update_object(
    connection: Connection,
    actor: UUID,
    unit_id: UUID,
    object_type: str,
    object_id: UUID,
    at: datetime,
) -> None:
    action = {
        "ticket": ManagementAction.TASK_VIEW,
        "work_package": ManagementAction.TASK_VIEW,
        "calendar": ManagementAction.CALENDAR_VIEW_AVAILABILITY,
        "grant": ManagementAction.WORK_UPDATE_VIEW,
    }.get(object_type)
    if action is None:
        raise WorkspaceRecordDenied
    require_action(connection, actor, unit_id, action, at)
    object_query = {
        "ticket": (
            "SELECT 1 FROM team_task_ownership WHERE ticket_id=:object_id "
            "AND owning_unit_id=:unit_id LIMIT 1"
        ),
        "work_package": (
            "SELECT 1 FROM canonical_work_packages WHERE package_id=:object_id "
            "AND owning_unit_id=:unit_id LIMIT 1"
        ),
        "calendar": (
            "SELECT 1 FROM calendar_event_scopes WHERE event_id=:object_id "
            "AND unit_id=:unit_id LIMIT 1"
        ),
        "grant": (
            "SELECT 1 FROM team_management_grants WHERE grant_id=:object_id "
            "AND root_unit_id=:unit_id LIMIT 1"
        ),
    }[object_type]
    if (
        connection.execute(text(object_query), {"object_id": object_id, "unit_id": unit_id}).first()
        is None
    ):
        raise WorkspaceRecordDenied


def require_link_source(
    connection: Connection,
    actor: UUID,
    unit_id: UUID,
    source_type: str,
    source_id: UUID,
    at: datetime,
) -> None:
    if source_type not in {"ticket", "work_package"}:
        raise WorkspaceRecordDenied
    require_action(connection, actor, unit_id, ManagementAction.TASK_VIEW, at)
    query = {
        "ticket": (
            "SELECT 1 FROM team_task_ownership WHERE ticket_id=:source_id "
            "AND owning_unit_id=:unit_id LIMIT 1"
        ),
        "work_package": (
            "SELECT 1 FROM canonical_work_packages WHERE package_id=:source_id "
            "AND owning_unit_id=:unit_id LIMIT 1"
        ),
    }[source_type]
    if (
        connection.execute(text(query), {"source_id": source_id, "unit_id": unit_id}).first()
        is None
    ):
        raise WorkspaceRecordDenied
