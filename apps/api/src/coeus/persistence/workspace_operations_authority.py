"""Bounded current-authority resolution for workspace operations."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.workspace_operations import WorkspaceOperationsDenied, WorkspaceScope
from coeus.domain.workspace_productivity import WorkspaceRecordDenied
from coeus.persistence.organisation_authority_validation import validate_lineage
from coeus.persistence.workspace_productivity_authority import require_active_actor


@dataclass(frozen=True)
class WorkspaceAuthority:
    grant_id: UUID
    grant_version: int
    unit_ids: tuple[UUID, ...]


def resolve_workspace_authority(
    connection: Connection,
    actor: UUID,
    root_unit_id: UUID,
    action: ManagementAction,
    scope: WorkspaceScope,
    at: datetime,
    *,
    lock: bool = False,
) -> WorkspaceAuthority:
    try:
        require_active_actor(connection, actor, lock=lock)
    except WorkspaceRecordDenied as error:
        # Callers of this module handle its own refusal, so an inactive account
        # must not surface a neighbouring module's exception as a server error.
        raise WorkspaceOperationsDenied from error
    query = _GRANTS_LOCKED if lock else _GRANTS
    rows = tuple(
        connection.execute(
            text(query),
            {"actor": actor, "action": action.value, "at": at},
        ).mappings()
    )
    if len(rows) > 200:
        raise WorkspaceOperationsDenied
    for row in rows:
        if scope is WorkspaceScope.DESCENDANTS and not bool(row["include_descendants"]):
            continue
        grant_id = UUID(str(row["grant_id"]))
        try:
            validate_lineage(connection, grant_id, actor, root_unit_id, action, at)
        except OrganisationAuthorityDenied:
            continue
        unit_ids = _unit_ids(connection, root_unit_id, scope)
        return WorkspaceAuthority(grant_id, int(row["version"]), unit_ids)
    raise WorkspaceOperationsDenied


def has_effective_membership(
    connection: Connection, actor: UUID, unit_id: UUID, at: datetime
) -> bool:
    """Whether the actor is currently posted to exactly this unit.

    A posting is not management authority and must never be treated as one. It
    is the basis for the single read a member is entitled to without a grant:
    the roster of their own team, at direct scope only.
    """
    try:
        require_active_actor(connection, actor)
    except WorkspaceRecordDenied:
        return False
    row = connection.execute(text(_MEMBERSHIP), {"actor": actor, "unit": unit_id, "at": at}).first()
    return row is not None


def _unit_ids(
    connection: Connection, root_unit_id: UUID, scope: WorkspaceScope
) -> tuple[UUID, ...]:
    if scope is WorkspaceScope.DIRECT:
        exists = connection.execute(
            text("SELECT 1 FROM organisation_units WHERE unit_id=:unit AND is_active"),
            {"unit": root_unit_id},
        ).first()
        if exists is None:
            raise WorkspaceOperationsDenied
        return (root_unit_id,)
    rows = tuple(
        connection.execute(
            text(
                "SELECT c.descendant_unit_id FROM organisation_unit_closure c "
                "JOIN organisation_units u ON u.unit_id=c.descendant_unit_id "
                "WHERE c.ancestor_unit_id=:unit AND c.depth<=12 AND u.is_active "
                "ORDER BY c.depth,c.descendant_unit_id LIMIT 1001"
            ),
            {"unit": root_unit_id},
        )
    )
    if not rows or len(rows) > 1000:
        raise WorkspaceOperationsDenied
    return tuple(UUID(str(row[0])) for row in rows)


_GRANTS = """
SELECT grant_id,version,include_descendants FROM team_management_grants
WHERE manager_user_id=:actor AND action=:action
AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until)
AND (revoked_at IS NULL OR :at<revoked_at) ORDER BY grant_id LIMIT 201
"""
_GRANTS_LOCKED = _GRANTS + " FOR UPDATE"

_MEMBERSHIP = """
SELECT 1 FROM team_memberships m
JOIN organisation_units u ON u.unit_id = m.unit_id
WHERE m.user_id=:actor AND m.unit_id=:unit AND m.state='active'
AND m.valid_from<=:at AND (m.valid_until IS NULL OR :at<m.valid_until)
AND u.is_active AND u.valid_from<=:at AND (u.valid_until IS NULL OR :at<u.valid_until)
LIMIT 1
"""
