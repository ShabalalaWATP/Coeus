"""Versioned PostgreSQL repository for canonical team task ownership."""

from datetime import date, datetime
from enum import StrEnum
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, RowMapping

from coeus.domain.team_task_ownership import (
    TeamTaskOwnership,
    TeamTaskOwnershipState,
    WorkflowLeg,
)


class PostgresTeamTaskOwnershipRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_ownership(self, ticket_id: UUID, workflow_leg: WorkflowLeg) -> TeamTaskOwnership | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM team_task_ownership WHERE ticket_id=:ticket_id "
                        "AND workflow_leg=:workflow_leg"
                    ),
                    {"ticket_id": ticket_id, "workflow_leg": workflow_leg.value},
                )
                .mappings()
                .first()
            )
        return None if row is None else _ownership(row)

    def list_unit_ownership(
        self, unit_id: UUID, *, limit: int = 100
    ) -> tuple[TeamTaskOwnership, ...]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between one and 200")
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT * FROM team_task_ownership WHERE owning_unit_id=:unit_id "
                        "ORDER BY target_date NULLS LAST, ticket_id LIMIT :limit"
                    ),
                    {"unit_id": unit_id, "limit": limit},
                )
                .mappings()
                .all()
            )
        return tuple(_ownership(row) for row in rows)

    def save_ownership(
        self, ownership: TeamTaskOwnership, *, expected_version: int | None
    ) -> TeamTaskOwnership:
        if expected_version is not None and expected_version < 1:
            raise ValueError("expected_version must be positive")
        expected_next = 1 if expected_version is None else expected_version + 1
        if ownership.version != expected_next:
            raise ValueError("ownership version must be the next expected version")
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    text(_UPSERT),
                    {**_params(ownership), "expected_version": expected_version},
                )
                .mappings()
                .first()
            )
        if row is None:
            raise ValueError("team task ownership version or identity conflict")
        return _ownership(row)


_UPSERT = """
INSERT INTO team_task_ownership(
 ownership_id,ticket_id,workflow_leg,owning_unit_id,manager_user_id,state,accepted_at,
 target_date,topology_revision_id,capability_policy_version,version,history_reference,
 provenance,reason,created_at)
VALUES (:ownership_id,:ticket_id,:workflow_leg,:owning_unit_id,:manager_user_id,:state,
 :accepted_at,:target_date,:topology_revision_id,:capability_policy_version,:version,
 :history_reference,:provenance,:reason,:created_at)
ON CONFLICT (ticket_id,workflow_leg) DO UPDATE SET
 owning_unit_id=EXCLUDED.owning_unit_id, manager_user_id=EXCLUDED.manager_user_id,
 state=EXCLUDED.state, accepted_at=EXCLUDED.accepted_at, target_date=EXCLUDED.target_date,
 topology_revision_id=EXCLUDED.topology_revision_id,
 capability_policy_version=EXCLUDED.capability_policy_version,
 version=EXCLUDED.version, history_reference=EXCLUDED.history_reference,
 provenance=EXCLUDED.provenance, reason=EXCLUDED.reason, updated_at=now()
WHERE team_task_ownership.ownership_id=EXCLUDED.ownership_id
 AND team_task_ownership.version=:expected_version
 AND EXCLUDED.version=:expected_version + 1
RETURNING *
"""


def _params(value: TeamTaskOwnership) -> dict[str, object]:
    return {
        key: item.value if isinstance(item, StrEnum) else item for key, item in vars(value).items()
    }


def _ownership(row: RowMapping) -> TeamTaskOwnership:
    return TeamTaskOwnership(
        ownership_id=UUID(str(row["ownership_id"])),
        ticket_id=UUID(str(row["ticket_id"])),
        workflow_leg=WorkflowLeg(str(row["workflow_leg"])),
        owning_unit_id=UUID(str(row["owning_unit_id"])),
        manager_user_id=(
            None if row["manager_user_id"] is None else UUID(str(row["manager_user_id"]))
        ),
        state=TeamTaskOwnershipState(str(row["state"])),
        accepted_at=cast(datetime | None, row["accepted_at"]),
        target_date=cast(date | None, row["target_date"]),
        topology_revision_id=UUID(str(row["topology_revision_id"])),
        capability_policy_version=int(str(row["capability_policy_version"])),
        version=int(str(row["version"])),
        history_reference=UUID(str(row["history_reference"])),
        provenance=str(row["provenance"]),
        reason=str(row["reason"]),
        created_at=cast(datetime, row["created_at"]),
    )
