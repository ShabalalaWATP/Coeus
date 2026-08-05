"""Read-first Sprint 24 projection and reservation recovery."""

import json
from dataclasses import asdict, dataclass, replace
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from coeus.persistence.database_url import synchronous_database_url

_MAX_ISSUES = 500
RepairAction = Literal["inspect", "repair-reservations"]


@dataclass(frozen=True)
class RepairIssue:
    code: str
    object_id: str
    repairable: bool


@dataclass(frozen=True)
class OrganisationCapacityRepairReport:
    topology_issues: tuple[RepairIssue, ...]
    ownership_issues: tuple[RepairIssue, ...]
    reservation_issues: tuple[RepairIssue, ...]
    truncated: bool = False
    changed_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def has_issues(self) -> bool:
        return self.truncated or any(
            (self.topology_issues, self.ownership_issues, self.reservation_issues)
        )


def inspect_or_repair_organisation_capacity(
    database_url: str,
    *,
    action: RepairAction = "inspect",
    operator_user_id: UUID | None = None,
    reason: str | None = None,
    reviewed: bool = False,
) -> OrganisationCapacityRepairReport:
    """Inspect drift, or repair only uniquely derived reservation lifecycle drift."""
    if action != "inspect" and (operator_user_id is None or not reason or not reviewed):
        raise ValueError("Reservation repair requires operator, reason and reviewed confirmation.")
    if reason and len(reason) > 500:
        raise ValueError("Repair reason exceeds 500 characters.")
    engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('coeus:sprint24-repair'))")
            )
            before = _inspect(connection)
            if action == "inspect":
                return before
            if before.truncated:
                raise RuntimeError("A truncated report cannot be repaired safely.")
            changed = _repair_reservations(connection, before.reservation_issues)
            if changed:
                _append_evidence(connection, operator_user_id, reason or "", changed)
            return replace(_inspect(connection), changed_count=len(changed))
    finally:
        engine.dispose()


def _inspect(connection: Connection) -> OrganisationCapacityRepairReport:
    topology, topology_more = _issues(connection, _TOPOLOGY_DRIFT, repairable=False)
    ownership, ownership_more = _issues(connection, _OWNERSHIP_DRIFT, repairable=False)
    reservations, reservation_more = _issues(connection, _RESERVATION_DRIFT)
    return OrganisationCapacityRepairReport(
        topology,
        ownership,
        reservations,
        topology_more or ownership_more or reservation_more,
    )


def _issues(
    connection: Connection, statement: str, *, repairable: bool | None = None
) -> tuple[tuple[RepairIssue, ...], bool]:
    rows = tuple(connection.execute(text(statement), {"limit": _MAX_ISSUES + 1}).mappings())
    issues = tuple(
        RepairIssue(
            str(row["code"]),
            str(row["object_id"]),
            bool(row["repairable"]) if repairable is None else repairable,
        )
        for row in rows[:_MAX_ISSUES]
    )
    return issues, len(rows) > _MAX_ISSUES


def _repair_reservations(
    connection: Connection, issues: tuple[RepairIssue, ...]
) -> tuple[str, ...]:
    if any(not issue.repairable for issue in issues):
        raise RuntimeError("Non-repairable reservation drift requires manual disposition.")
    changed: list[str] = []
    for issue in issues:
        if issue.code not in {"expired_hold", "terminal_package_reservation"}:
            raise RuntimeError("Unsupported reservation drift requires manual disposition.")
        target_state = "expired" if issue.code == "expired_hold" else "released"
        row = connection.execute(
            text(_REPAIR_RESERVATION),
            {
                "reservation_id": UUID(issue.object_id),
                "target_state": target_state,
                "issue_code": issue.code,
            },
        ).first()
        if row is not None:
            changed.append(issue.object_id)
    return tuple(changed)


def _append_evidence(
    connection: Connection,
    operator_user_id: UUID | None,
    reason: str,
    changed_ids: tuple[str, ...],
) -> None:
    if operator_user_id is None:
        raise ValueError("Operator identity is required for repair evidence.")
    event_id = uuid4()
    metadata = json.dumps(
        {"changed_count": len(changed_ids), "reservation_ids": changed_ids, "reason": reason},
        sort_keys=True,
    )
    connection.execute(
        text(_AUDIT),
        {"event_id": event_id, "actor": operator_user_id, "metadata": metadata},
    )
    connection.execute(
        text(_OUTBOX),
        {"event_id": uuid4(), "aggregate_id": event_id, "payload": metadata},
    )


_TOPOLOGY_DRIFT = """
WITH RECURSIVE expected(ancestor_unit_id, descendant_unit_id, depth) AS (
  SELECT unit_id, unit_id, 0 FROM organisation_units
  UNION ALL
  SELECT expected.ancestor_unit_id, child.unit_id, expected.depth + 1
  FROM expected
  JOIN organisation_units child ON child.parent_unit_id=expected.descendant_unit_id
  WHERE expected.depth < 12
), drift AS (
  SELECT
    CASE
      WHEN actual.ancestor_unit_id IS NULL THEN 'closure_row_missing'
      WHEN expected.ancestor_unit_id IS NULL THEN 'closure_row_unexpected'
      ELSE 'closure_depth_mismatch'
    END AS code,
    coalesce(expected.descendant_unit_id, actual.descendant_unit_id)::text AS object_id
  FROM expected
  FULL OUTER JOIN organisation_unit_closure actual
    USING (ancestor_unit_id, descendant_unit_id)
  WHERE actual.ancestor_unit_id IS NULL OR expected.ancestor_unit_id IS NULL
     OR actual.depth<>expected.depth
)
SELECT code, object_id FROM drift ORDER BY code, object_id LIMIT :limit
"""

_OWNERSHIP_DRIFT = """
SELECT
  CASE
    WHEN ownership.ownership_id IS NULL THEN 'task_ownership_missing'
    ELSE 'task_ownership_unit_mismatch'
  END AS code,
  package.package_id::text AS object_id
FROM canonical_work_packages package
LEFT JOIN team_task_ownership ownership
  ON ownership.ticket_id=package.ticket_id AND ownership.workflow_leg=package.workflow_leg
WHERE ownership.ownership_id IS NULL OR ownership.owning_unit_id<>package.owning_unit_id
UNION ALL
SELECT 'task_ownership_ticket_missing', ownership.ownership_id::text
FROM team_task_ownership ownership
LEFT JOIN coeus_ticket_aggregates ticket ON ticket.ticket_id=ownership.ticket_id
WHERE ticket.ticket_id IS NULL
ORDER BY code, object_id LIMIT :limit
"""

_RESERVATION_DRIFT = """
SELECT
  CASE
    WHEN reservation.ticket_id<>package.ticket_id
      OR reservation.workflow_leg<>package.workflow_leg
      OR reservation.user_id IS DISTINCT FROM package.accountable_user_id
      THEN 'reservation_package_mismatch'
    WHEN reservation.state='held' AND reservation.expires_at<=transaction_timestamp()
      THEN 'expired_hold'
    ELSE 'terminal_package_reservation'
  END AS code,
  reservation.reservation_id::text AS object_id,
  CASE
    WHEN reservation.ticket_id<>package.ticket_id
      OR reservation.workflow_leg<>package.workflow_leg
      OR reservation.user_id IS DISTINCT FROM package.accountable_user_id
      THEN false
    ELSE true
  END AS repairable
FROM capacity_reservations reservation
JOIN canonical_work_packages package ON package.package_id=reservation.package_id
WHERE reservation.state IN ('held','active') AND (
  reservation.ticket_id<>package.ticket_id
  OR reservation.workflow_leg<>package.workflow_leg
  OR reservation.user_id IS DISTINCT FROM package.accountable_user_id
  OR (reservation.state='held' AND reservation.expires_at<=transaction_timestamp())
  OR package.state IN ('complete','cancelled')
)
ORDER BY code, object_id LIMIT :limit
"""

_REPAIR_RESERVATION = """
UPDATE capacity_reservations reservation
SET state=:target_state, version=reservation.version+1, updated_at=transaction_timestamp()
FROM canonical_work_packages package
WHERE reservation.reservation_id=:reservation_id
  AND package.package_id=reservation.package_id
  AND reservation.ticket_id=package.ticket_id
  AND reservation.workflow_leg=package.workflow_leg
  AND reservation.user_id IS NOT DISTINCT FROM package.accountable_user_id
  AND reservation.state IN ('held','active')
  AND (
    (:issue_code='expired_hold' AND reservation.state='held'
      AND reservation.expires_at<=transaction_timestamp())
    OR (:issue_code='terminal_package_reservation'
      AND package.state IN ('complete','cancelled'))
  )
RETURNING reservation.reservation_id
"""

_AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,'capacity_reservation_drift_repaired',transaction_timestamp(),
        :actor,CAST(:metadata AS jsonb))
"""

_OUTBOX = """
INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload)
VALUES (:event_id,:aggregate_id,1,'capacity_reservation_drift_repaired',CAST(:payload AS jsonb))
"""
