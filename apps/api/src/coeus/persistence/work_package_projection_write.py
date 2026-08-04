"""Atomic projection of ticket work packages into the canonical team ledger."""

import json
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, delivery_route_for_leg
from coeus.domain.tickets import AnalystAssignment, AnalystWorkPackage, TicketRecord

_PROVENANCE = "ticket-assignment-work-package-v1"


def write_assignment_work_packages(
    connection: Connection,
    ticket: TicketRecord,
    ownership: AssignmentOwnershipIntent,
    *,
    only_missing: bool = False,
) -> tuple[UUID, ...]:
    """Project packages with one accountable current member of the owning leaf team."""
    if not ticket.work_packages:
        return ()
    now = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
    assert isinstance(now, datetime)
    assignments = _active_assignments(ticket, ownership)
    _lock_and_validate_memberships(connection, assignments, ownership.owning_unit_id, now)
    written: list[UUID] = []
    for index, package in enumerate(sorted(ticket.work_packages, key=_package_order)):
        if only_missing and _package_exists(connection, package.package_id):
            continue
        owner = assignments[index % len(assignments)]
        version = _upsert_package(connection, package, ownership, owner, now)
        _reconcile_participants(
            connection,
            package.package_id,
            owner.analyst_user_id,
            tuple(item.analyst_user_id for item in assignments),
            now,
        )
        _append_history(connection, package, owner, version, now)
        written.append(package.package_id)
    return tuple(written)


def _package_exists(connection: Connection, package_id: UUID) -> bool:
    return (
        connection.execute(
            text("SELECT 1 FROM canonical_work_packages WHERE package_id=:package_id"),
            {"package_id": package_id},
        ).scalar_one_or_none()
        is not None
    )


def _active_assignments(
    ticket: TicketRecord,
    ownership: AssignmentOwnershipIntent,
) -> tuple[AnalystAssignment, ...]:
    route = delivery_route_for_leg(ownership.workflow_leg)
    assignments = tuple(
        assignment
        for assignment in ticket.analyst_assignments
        if assignment.active
        and assignment.route.value == route
        and assignment.team_id == ownership.owning_unit_id
    )
    if not assignments:
        raise ValueError("work packages require an active assignment in the owning team")
    if len({item.analyst_user_id for item in assignments}) != len(assignments):
        raise ValueError("work package assignment contains duplicate accountable candidates")
    return assignments


def _lock_and_validate_memberships(
    connection: Connection,
    assignments: tuple[AnalystAssignment, ...],
    unit_id: UUID,
    now: datetime,
) -> None:
    leaf = connection.execute(
        text(_LEAF_UNIT), {"unit_id": unit_id, "at": now}
    ).scalar_one_or_none()
    if leaf is None:
        raise ValueError("work packages require an active leaf delivery team")
    for assignment in assignments:
        rows = tuple(
            connection.execute(
                text(_CURRENT_MEMBERSHIP),
                {"user_id": assignment.analyst_user_id, "at": now},
            ).mappings()
        )
        if len(rows) != 1 or rows[0]["unit_id"] != unit_id or not rows[0]["assignment_eligible"]:
            raise ValueError("work package owner lacks one eligible home membership in the team")


def _upsert_package(
    connection: Connection,
    package: AnalystWorkPackage,
    ownership: AssignmentOwnershipIntent,
    owner: AnalystAssignment,
    now: datetime,
) -> int:
    row = (
        connection.execute(
            text(_UPSERT_PACKAGE),
            {
                "package_id": package.package_id,
                "ticket_id": package.ticket_id,
                "workflow_leg": ownership.workflow_leg.value,
                "unit_id": ownership.owning_unit_id,
                "owner_id": owner.analyst_user_id,
                "title": package.title,
                "state": _canonical_state(package.status.value),
                "sort_order": package.sort_order,
                "provenance": _PROVENANCE,
                "now": now,
            },
        )
        .mappings()
        .one()
    )
    return int(row["version"])


def _reconcile_participants(
    connection: Connection,
    package_id: UUID,
    owner_id: UUID,
    assignment_user_ids: tuple[UUID, ...],
    now: datetime,
) -> None:
    removed = tuple(
        connection.execute(
            text(_END_REMOVED_PARTICIPANTS),
            {
                "package_id": package_id,
                "owner_id": owner_id,
                "assignment_user_ids": list(assignment_user_ids),
                "now": now,
            },
        ).scalars()
    )
    if removed:
        connection.execute(
            text(_RELEASE_REMOVED_RESERVATIONS),
            {"package_id": package_id, "user_ids": list(removed), "now": now},
        )
    connection.execute(
        text(_UPSERT_ACCOUNTABLE),
        {"package_id": package_id, "owner_id": owner_id, "now": now},
    )


def _append_history(
    connection: Connection,
    package: AnalystWorkPackage,
    owner: AnalystAssignment,
    version: int,
    now: datetime,
) -> None:
    history_id = uuid5(NAMESPACE_URL, f"coeus:work-package:{package.package_id}:{version}")
    connection.execute(
        text(_INSERT_HISTORY),
        {
            "history_id": history_id,
            "package_id": package.package_id,
            "version": version,
            "actor_id": owner.assigned_by_user_id,
            "evidence": json.dumps(
                {"accountable_user_id": str(owner.analyst_user_id), "source": _PROVENANCE}
            ),
            "now": now,
        },
    )


def _canonical_state(status: str) -> str:
    return "complete" if status == "complete" else "pending"


def _package_order(package: AnalystWorkPackage) -> tuple[int, str]:
    return package.sort_order, str(package.package_id)


_LEAF_UNIT = """
SELECT unit.unit_id
FROM organisation_units unit
WHERE unit.unit_id=:unit_id AND unit.is_active
  AND unit.valid_from<=:at AND (unit.valid_until IS NULL OR :at<unit.valid_until)
  AND NOT EXISTS (
    SELECT 1 FROM organisation_units child
    WHERE child.parent_unit_id=unit.unit_id AND child.is_active
      AND child.valid_from<=:at AND (child.valid_until IS NULL OR :at<child.valid_until)
  )
FOR UPDATE
"""

_CURRENT_MEMBERSHIP = """
SELECT membership_id,unit_id,assignment_eligible
FROM team_memberships
WHERE user_id=:user_id AND state='active'
  AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until)
FOR UPDATE
"""

_UPSERT_PACKAGE = """
INSERT INTO canonical_work_packages(
 package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,title,state,
 sort_order,version,provenance,created_at,updated_at)
VALUES (
 :package_id,:ticket_id,:workflow_leg,:unit_id,:owner_id,:title,:state,
 :sort_order,1,:provenance,:now,:now)
ON CONFLICT (package_id) DO UPDATE SET
 owning_unit_id=EXCLUDED.owning_unit_id,accountable_user_id=EXCLUDED.accountable_user_id,
 title=EXCLUDED.title,state=EXCLUDED.state,sort_order=EXCLUDED.sort_order,
 version=canonical_work_packages.version+1,provenance=EXCLUDED.provenance,updated_at=EXCLUDED.updated_at
WHERE canonical_work_packages.ticket_id=EXCLUDED.ticket_id
  AND canonical_work_packages.workflow_leg=EXCLUDED.workflow_leg
RETURNING version
"""

_END_REMOVED_PARTICIPANTS = """
UPDATE work_package_participants
SET active=false,ended_at=:now
WHERE package_id=:package_id AND active AND (
  (role='accountable' AND user_id<>:owner_id) OR
  (role='contributor' AND NOT (user_id=ANY(CAST(:assignment_user_ids AS uuid[]))))
)
RETURNING user_id
"""

_RELEASE_REMOVED_RESERVATIONS = """
UPDATE capacity_reservations SET state='released',version=version+1,updated_at=:now
WHERE package_id=:package_id AND user_id=ANY(CAST(:user_ids AS uuid[]))
  AND state IN ('held','active')
"""

_UPSERT_ACCOUNTABLE = """
INSERT INTO work_package_participants(package_id,user_id,role,active,created_at,ended_at)
VALUES (:package_id,:owner_id,'accountable',true,:now,NULL)
ON CONFLICT (package_id,user_id,role) DO UPDATE SET active=true,ended_at=NULL
"""

_INSERT_HISTORY = """
INSERT INTO work_package_history(
 history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at)
VALUES (
 :history_id,:package_id,:version,:actor_id,'assignment_projection',
 CAST(:evidence AS jsonb),:now)
ON CONFLICT (package_id,version) DO NOTHING
"""
