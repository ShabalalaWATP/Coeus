"""Bounded, idempotent reconciliation of legacy active assignments."""

import json
from collections import defaultdict
from datetime import date, datetime
from hashlib import sha256
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.task_ownership_reconciliation import (
    TaskOwnershipReconciliationStore,
)
from coeus.domain.organisation_reconciliation import PROJECTION_ACTOR_ID
from coeus.domain.task_ownership_reconciliation import (
    TaskOwnershipReconciliationLimit,
    TaskOwnershipReconciliationResult,
)
from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.domain.tickets import AnalystAssignment, RoutingRoute, TicketRecord
from coeus.persistence.codec import decode_value
from coeus.persistence.team_task_assignment_write import write_assignment_ownership
from coeus.persistence.work_package_projection_write import write_assignment_work_packages

_NAMESPACE = "legacy-ticket-assignment-ownership-v1"
_MAX_TICKETS = 5_000


class PostgresTaskOwnershipReconciliationStore(TaskOwnershipReconciliationStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def reconcile(self) -> TaskOwnershipReconciliationResult:
        with self._engine.begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:namespace,0))"),
                {"namespace": _NAMESPACE},
            )
            as_of = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
            rows = tuple(connection.execute(text(_TICKETS), {"limit": _MAX_TICKETS + 1}).mappings())
            if len(rows) > _MAX_TICKETS:
                raise TaskOwnershipReconciliationLimit(
                    "historical assignment reconciliation exceeds the automatic batch limit"
                )
            digest = _digest(rows)
            checkpoint_id = uuid5(NAMESPACE_URL, f"coeus:{_NAMESPACE}:{digest}")
            previous = _completed(connection, checkpoint_id)
            if previous is not None:
                return _stored_result(previous, checkpoint_id, as_of)
            _start(connection, checkpoint_id, digest, as_of)
            created, existing, findings = _reconcile_rows(connection, checkpoint_id, as_of, rows)
            result = TaskOwnershipReconciliationResult(
                checkpoint_id, as_of, len(rows), created, existing, findings
            )
            _complete(connection, result)
            return result


def _reconcile_rows(
    connection: Connection,
    checkpoint_id: UUID,
    as_of: datetime,
    rows: tuple[RowMapping, ...],
) -> tuple[int, int, int]:
    created = existing = findings = 0
    for row in rows:
        ticket = decode_value(dict(row["payload"]))
        if not isinstance(ticket, TicketRecord) or str(ticket.ticket_id) != str(row["ticket_id"]):
            _finding(connection, checkpoint_id, as_of, str(row["ticket_id"]), "invalid_ticket")
            findings += 1
            continue
        for route, assignments in _active_by_route(ticket).items():
            leg = WorkflowLeg.RFA if route is RoutingRoute.RFA else WorkflowLeg.CM_COLLECTION
            source = f"{ticket.ticket_id}:{leg.value}"
            team_ids = {item.team_id for item in assignments}
            if None in team_ids or len(team_ids) != 1:
                _finding(connection, checkpoint_id, as_of, source, "ownership_ambiguous")
                findings += 1
                continue
            # The ambiguity check above already refused a None or a split set.
            team_id = cast(UUID, next(iter(team_ids)))
            current = connection.execute(
                text(
                    "SELECT owning_unit_id FROM team_task_ownership "
                    "WHERE ticket_id=:ticket_id AND workflow_leg=:leg FOR UPDATE"
                ),
                {"ticket_id": ticket.ticket_id, "leg": leg.value},
            ).scalar_one_or_none()
            latest = max(assignments, key=lambda item: (item.created_at, str(item.assignment_id)))
            intent = AssignmentOwnershipIntent(
                team_id,
                leg,
                latest.assigned_by_user_id,
                uuid5(NAMESPACE_URL, f"coeus:backfill:{source}:{row['canonical_hash']}"),
                _target_date(ticket),
                _NAMESPACE,
            )
            if current is not None:
                if str(current) != str(team_id):
                    _finding(connection, checkpoint_id, as_of, source, "ownership_conflict")
                    findings += 1
                else:
                    if _backfill_existing_packages(
                        connection, checkpoint_id, as_of, source, ticket, intent
                    ):
                        findings += 1
                    else:
                        existing += 1
                continue
            try:
                write_assignment_ownership(connection, str(ticket.ticket_id), intent)
                write_assignment_work_packages(connection, ticket, intent, only_missing=True)
            except ValueError:
                _finding(connection, checkpoint_id, as_of, source, "delivery_authority_missing")
                findings += 1
            else:
                created += 1
    return created, existing, findings


def _backfill_existing_packages(
    connection: Connection,
    checkpoint_id: UUID,
    as_of: datetime,
    source: str,
    ticket: TicketRecord,
    intent: AssignmentOwnershipIntent,
) -> bool:
    try:
        write_assignment_work_packages(connection, ticket, intent, only_missing=True)
    except ValueError:
        _finding(connection, checkpoint_id, as_of, source, "package_backfill_failed")
        return True
    return False


def _active_by_route(ticket: TicketRecord) -> dict[RoutingRoute, tuple[AnalystAssignment, ...]]:
    grouped: dict[RoutingRoute, list[AnalystAssignment]] = defaultdict(list)
    for assignment in ticket.analyst_assignments:
        if assignment.active and assignment.route in {RoutingRoute.RFA, RoutingRoute.CM}:
            grouped[assignment.route].append(assignment)
    return {route: tuple(items) for route, items in grouped.items()}


def _target_date(ticket: TicketRecord) -> date | None:
    if not ticket.intake.deadline:
        return None
    try:
        return datetime.fromisoformat(ticket.intake.deadline).date()
    except ValueError:
        return None


def _digest(rows: tuple[RowMapping, ...]) -> str:
    material = "\n".join(f"{row['ticket_id']}:{row['canonical_hash']}" for row in rows).encode()
    return sha256(material).hexdigest()


def _completed(connection: Connection, checkpoint_id: UUID) -> RowMapping | None:
    return (
        connection.execute(
            text(
                "SELECT cursor FROM organisation_reconciliation_checkpoints "
                "WHERE checkpoint_id=:checkpoint_id AND status='completed'"
            ),
            {"checkpoint_id": checkpoint_id},
        )
        .mappings()
        .first()
    )


def _stored_result(
    row: RowMapping, checkpoint_id: UUID, as_of: datetime
) -> TaskOwnershipReconciliationResult:
    cursor = dict(row["cursor"])
    return TaskOwnershipReconciliationResult(
        checkpoint_id,
        as_of,
        int(cursor["scanned_tickets"]),
        int(cursor["created_ownerships"]),
        int(cursor["existing_ownerships"]),
        int(cursor["findings"]),
        True,
    )


def _finding(
    connection: Connection,
    checkpoint_id: UUID,
    as_of: datetime,
    source: str,
    code: str,
) -> None:
    connection.execute(
        text(_FINDING),
        {
            "finding_id": uuid5(NAMESPACE_URL, f"coeus:{checkpoint_id}:{code}:{source}"),
            "checkpoint_id": checkpoint_id,
            "code": code,
            "source": source,
            "details": json.dumps({"requires_manual_disposition": True}),
            "created_at": as_of,
        },
    )


def _start(connection: Connection, checkpoint_id: UUID, digest: str, as_of: datetime) -> None:
    connection.execute(
        text(_CHECKPOINT_START),
        {
            "checkpoint_id": checkpoint_id,
            "namespace": _NAMESPACE,
            "digest": digest,
            "as_of": as_of,
        },
    )


def _complete(
    connection: Connection,
    result: TaskOwnershipReconciliationResult,
) -> None:
    cursor = {
        "scanned_tickets": result.scanned_tickets,
        "created_ownerships": result.created_ownerships,
        "existing_ownerships": result.existing_ownerships,
        "findings": result.findings,
    }
    connection.execute(
        text(_CHECKPOINT_COMPLETE),
        {
            "checkpoint_id": result.checkpoint_id,
            "cursor": json.dumps(cursor, sort_keys=True),
            "as_of": result.as_of,
        },
    )
    evidence = json.dumps({"checkpoint_id": str(result.checkpoint_id), **cursor}, sort_keys=True)
    connection.execute(
        text(_AUDIT),
        {
            "event_id": uuid5(NAMESPACE_URL, f"coeus:{result.checkpoint_id}:audit"),
            "as_of": result.as_of,
            "actor": PROJECTION_ACTOR_ID,
            "metadata": evidence,
        },
    )


_TICKETS = """
SELECT ticket_id,payload,canonical_hash FROM coeus_ticket_aggregates
WHERE state IN ('ANALYST_ASSIGNMENT','ANALYST_IN_PROGRESS','MANAGER_APPROVAL',
 'QC_REVIEW','REWORK_REQUIRED','JIOC_INTERVENTION_HOLD')
ORDER BY ticket_id LIMIT :limit
"""

_CHECKPOINT_START = """
INSERT INTO organisation_reconciliation_checkpoints(
 checkpoint_id,source_namespace,source_digest,status,cursor,started_at,completed_at)
VALUES (:checkpoint_id,:namespace,:digest,'running','{}'::jsonb,:as_of,NULL)
ON CONFLICT (checkpoint_id) DO NOTHING
"""

_CHECKPOINT_COMPLETE = """
UPDATE organisation_reconciliation_checkpoints
SET status='completed',cursor=CAST(:cursor AS jsonb),completed_at=:as_of,updated_at=:as_of
WHERE checkpoint_id=:checkpoint_id AND status='running'
"""

_FINDING = """
INSERT INTO organisation_reconciliation_findings(
 finding_id,checkpoint_id,finding_code,severity,source_identifier,details,created_at)
VALUES (:finding_id,:checkpoint_id,:code,'blocking',:source,CAST(:details AS jsonb),:created_at)
ON CONFLICT (finding_id) DO NOTHING
"""

_AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,'task_ownership_reconciled',:as_of,:actor,CAST(:metadata AS jsonb))
ON CONFLICT (event_id) DO NOTHING
"""
