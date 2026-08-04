"""Atomic canonical ownership projection for analyst assignment commits."""

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.team_task_ownership import (
    AssignmentOwnershipIntent,
    delivery_route_for_leg,
)


def write_assignment_ownership(
    connection: Connection,
    ticket_id: str,
    ownership: AssignmentOwnershipIntent,
) -> int:
    """Validate the current delivery authority and upsert one active leg owner."""
    now = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
    assert isinstance(now, datetime)
    authority = (
        connection.execute(
            text(_AUTHORITY),
            {
                "unit_id": ownership.owning_unit_id,
                "route": delivery_route_for_leg(ownership.workflow_leg),
                "effective_at": now,
            },
        )
        .mappings()
        .first()
    )
    if authority is None:
        raise ValueError("assignment team has no current canonical delivery authority")
    ownership_id = uuid5(NAMESPACE_URL, f"coeus:ownership:{ticket_id}:{ownership.workflow_leg}")
    row = (
        connection.execute(
            text(_UPSERT),
            {
                "ownership_id": ownership_id,
                "ticket_id": ticket_id,
                "workflow_leg": ownership.workflow_leg.value,
                "unit_id": ownership.owning_unit_id,
                "manager_id": ownership.manager_user_id,
                "accepted_at": now,
                "target_date": ownership.target_date,
                "revision_id": authority["revision_id"],
                "policy_version": authority["policy_version"],
                "history_reference": ownership.history_reference,
                "provenance": ownership.provenance,
                "created_at": now,
            },
        )
        .mappings()
        .one()
    )
    return int(row["version"])


_AUTHORITY = """
SELECT revision.revision_id, profile.policy_version
FROM organisation_units unit
JOIN team_delivery_profiles profile ON profile.unit_id=unit.unit_id
JOIN organisation_topology_revisions revision ON revision.unit_id=unit.unit_id
WHERE unit.unit_id=:unit_id AND unit.is_active
  AND unit.valid_from<=:effective_at
  AND (unit.valid_until IS NULL OR :effective_at<unit.valid_until)
  AND profile.is_active AND profile.route=:route
  AND revision.valid_from<=:effective_at
  AND (revision.valid_until IS NULL OR :effective_at<revision.valid_until)
ORDER BY revision.valid_from DESC
LIMIT 1
"""

_UPSERT = """
INSERT INTO team_task_ownership(
 ownership_id,ticket_id,workflow_leg,owning_unit_id,manager_user_id,state,accepted_at,
 target_date,topology_revision_id,capability_policy_version,version,history_reference,
 provenance,reason,created_at,updated_at)
VALUES (
 :ownership_id,CAST(:ticket_id AS uuid),:workflow_leg,:unit_id,:manager_id,'active',:accepted_at,
 :target_date,:revision_id,:policy_version,1,:history_reference,
 :provenance,'',:created_at,:created_at)
ON CONFLICT (ticket_id,workflow_leg) DO UPDATE SET
 owning_unit_id=EXCLUDED.owning_unit_id,manager_user_id=EXCLUDED.manager_user_id,
 state='active',accepted_at=EXCLUDED.accepted_at,target_date=EXCLUDED.target_date,
 topology_revision_id=EXCLUDED.topology_revision_id,
 capability_policy_version=EXCLUDED.capability_policy_version,
 version=team_task_ownership.version+1,history_reference=EXCLUDED.history_reference,
 provenance=EXCLUDED.provenance,reason='',updated_at=EXCLUDED.updated_at
RETURNING version
"""
