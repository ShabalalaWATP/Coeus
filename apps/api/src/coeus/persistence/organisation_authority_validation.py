"""Transactional grant-lineage validation shared by authority commands."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.jioc_principals import PrincipalKind, principal_kind
from coeus.domain.organisation import ManagementAction, OrganisationManagementGrant
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.persistence import organisation_authority_sql as sql


def lock_lineages(connection: Connection, grant_ids: tuple[UUID, ...]) -> None:
    ids = {
        UUID(str(row["grant_id"]))
        for grant_id in grant_ids
        for row in _lineage(connection, grant_id)
    }
    if not ids:
        raise OrganisationAuthorityDenied("authorising grant lineage is missing")
    connection.execute(
        text(
            "SELECT grant_id FROM team_management_grants "
            "WHERE grant_id = ANY(CAST(:grant_ids AS uuid[])) ORDER BY grant_id FOR UPDATE"
        ),
        {"grant_ids": sorted(ids, key=str)},
    ).all()


def validate_lineage(
    connection: Connection,
    grant_id: UUID,
    manager_id: UUID,
    target_unit_id: UUID,
    action: ManagementAction,
    at: datetime,
) -> RowMapping:
    rows = _lineage(connection, grant_id)
    if not rows or len(rows) > 3:
        raise OrganisationAuthorityDenied("authorising grant lineage is invalid")
    leaf = rows[0]
    if UUID(str(leaf["manager_user_id"])) != manager_id or str(leaf["action"]) != action.value:
        raise OrganisationAuthorityDenied("authorising grant does not match actor or action")
    if not _row_covers(connection, leaf, target_unit_id):
        raise OrganisationAuthorityDenied("authorising grant does not cover the target unit")
    for index, row in enumerate(rows):
        if not _row_effective(row, at):
            raise OrganisationAuthorityDenied("authorising grant lineage is not effective")
        source_id = row["source_grant_id"]
        if index == len(rows) - 1:
            if source_id is not None or int(str(row["delegation_depth"])) != 0:
                raise OrganisationAuthorityDenied("authorising grant lineage has no valid root")
            continue
        source = rows[index + 1]
        valid_link = (
            UUID(str(source_id)) == UUID(str(source["grant_id"]))
            and str(source["action"]) == str(row["action"])
            and UUID(str(row["created_by_user_id"])) == UUID(str(source["manager_user_id"]))
            and int(str(row["delegation_depth"])) == int(str(source["delegation_depth"])) + 1
            and (not bool(row["include_descendants"]) or bool(source["include_descendants"]))
            and _row_covers(connection, source, UUID(str(row["root_unit_id"])))
        )
        if not valid_link:
            raise OrganisationAuthorityDenied("authorising grant lineage link is invalid")
    _require_current_principals(connection, rows)
    return leaf


def validate_delegation(source: RowMapping, grant: OrganisationManagementGrant) -> None:
    if grant.created_by_user_id != UUID(str(source["manager_user_id"])):
        raise OrganisationAuthorityDenied("grant creator does not own its source grant")
    if grant.delegation_depth != int(str(source["delegation_depth"])) + 1:
        raise OrganisationAuthorityDenied("grant delegation depth is invalid")
    if grant.include_descendants and not bool(source["include_descendants"]):
        raise OrganisationAuthorityDenied("grant scope is broader than its source")
    source_until = source["valid_until"]
    if source_until is not None and (grant.valid_until is None or grant.valid_until > source_until):
        raise OrganisationAuthorityDenied("grant validity is broader than its source")


def grant_row(connection: Connection, grant_id: UUID) -> RowMapping | None:
    return (
        connection.execute(
            text("SELECT * FROM team_management_grants WHERE grant_id = :grant_id"),
            {"grant_id": grant_id},
        )
        .mappings()
        .first()
    )


def transaction_time(connection: Connection) -> datetime:
    value = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
    if not isinstance(value, datetime):
        raise RuntimeError("PostgreSQL did not return a transaction timestamp")
    return value


def _lineage(connection: Connection, grant_id: UUID) -> tuple[RowMapping, ...]:
    return tuple(connection.execute(text(sql.LINEAGE), {"grant_id": grant_id}).mappings())


def _row_effective(row: RowMapping, at: datetime) -> bool:
    return (
        row["valid_from"] <= at
        and (row["valid_until"] is None or at < row["valid_until"])
        and (row["revoked_at"] is None or at < row["revoked_at"])
    )


def _row_covers(connection: Connection, row: RowMapping, target: UUID) -> bool:
    root = UUID(str(row["root_unit_id"]))
    if root == target:
        return True
    if not bool(row["include_descendants"]):
        return False
    return (
        connection.execute(
            text(
                "SELECT 1 FROM organisation_unit_closure WHERE ancestor_unit_id = :root "
                "AND descendant_unit_id = :target LIMIT 1"
            ),
            {"root": root, "target": target},
        ).first()
        is not None
    )


def _require_current_principals(connection: Connection, rows: tuple[RowMapping, ...]) -> None:
    """Lock and validate every human grant holder at the commit boundary."""
    human_ids = sorted(
        {
            principal_id
            for row in rows
            for principal_id in (
                UUID(str(row["manager_user_id"])),
                UUID(str(row["created_by_user_id"])),
            )
            if principal_kind(principal_id) is PrincipalKind.HUMAN
        },
        key=str,
    )
    if not human_ids:
        return
    accounts = tuple(
        connection.execute(
            text(
                "SELECT user_id,is_active FROM identity_account_projection "
                "WHERE user_id=ANY(CAST(:user_ids AS uuid[])) ORDER BY user_id FOR UPDATE"
            ),
            {"user_ids": human_ids},
        ).mappings()
    )
    active_ids = {
        UUID(str(account["user_id"])) for account in accounts if bool(account["is_active"])
    }
    if active_ids != set(human_ids):
        raise OrganisationAuthorityDenied(
            "authorising grant lineage contains a missing or suspended human principal"
        )
