"""Synthetic fixture writes for the internal JIOC shadow grant."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.persistence.synthetic_fixture_plan import SyntheticFixturePlan
from coeus.repositories.synthetic_organisation_manifest import BASELINE, SyntheticUnitSpec


def insert_service_grants(
    connection: Connection,
    plan: SyntheticFixturePlan,
    units: dict[str, SyntheticUnitSpec],
    actor_user_id: UUID,
    occurred_at: datetime,
) -> None:
    for grant in plan.service_grants:
        connection.execute(
            text(
                "INSERT INTO team_management_grants"
                "(grant_id,manager_user_id,root_unit_id,action,include_descendants,"
                "valid_from,valid_until,revoked_at,created_by_user_id,reason,"
                "source_grant_id,delegation_depth,version,created_at,updated_at) VALUES "
                "(:grant_id,:principal_id,:root_id,:action,:include_descendants,"
                ":valid_from,NULL,NULL,:actor_id,:reason,NULL,0,1,"
                ":occurred_at,:occurred_at)"
            ),
            {
                "grant_id": grant.grant_id,
                "principal_id": grant.principal_id,
                "root_id": units[grant.unit_key].unit_id,
                "action": grant.action.value,
                "include_descendants": grant.include_descendants,
                "valid_from": BASELINE,
                "actor_id": actor_user_id,
                "reason": "Synthetic JIOC shadow-context authority.",
                "occurred_at": occurred_at,
            },
        )
