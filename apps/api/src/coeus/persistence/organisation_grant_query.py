"""Bounded PostgreSQL management-grant query helpers."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from coeus.domain.organisation import OrganisationManagementGrant
from coeus.persistence.organisation_grant_rows import decode_grant


def list_management_grants(
    engine: Engine,
    *,
    root_unit_id: UUID | None,
    manager_user_id: UUID | None,
    include_inactive: bool,
    limit: int,
) -> tuple[OrganisationManagementGrant, ...]:
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between one and 500")
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT * FROM team_management_grants "
                "WHERE (CAST(:root_id AS uuid) IS NULL "
                "OR root_unit_id=CAST(:root_id AS uuid)) "
                "AND (CAST(:manager_id AS uuid) IS NULL "
                "OR manager_user_id=CAST(:manager_id AS uuid)) "
                "AND (CAST(:include_inactive AS boolean) OR "
                "(valid_from<=transaction_timestamp() "
                "AND (valid_until IS NULL OR valid_until>transaction_timestamp()) "
                "AND (revoked_at IS NULL OR revoked_at>transaction_timestamp()))) "
                "ORDER BY root_unit_id,manager_user_id,action,grant_id LIMIT :limit"
            ),
            {
                "root_id": root_unit_id,
                "manager_id": manager_user_id,
                "include_inactive": include_inactive,
                "limit": limit,
            },
        ).mappings()
        return tuple(decode_grant(row) for row in rows)
