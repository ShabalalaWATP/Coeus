"""Fail-closed diagnosis and repair for retained-ticket capacity projections."""

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from coeus.domain.ticket_retention import ticket_consumes_capacity
from coeus.domain.tickets import TicketRecord
from coeus.persistence.audit_store import AUDIT_ORDER_INDEX_SQL, AUDIT_TABLE_SQL
from coeus.persistence.codec import decode_value
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.resource_lease_schema import RESOURCE_LEASE_SCHEMA_SQL
from coeus.persistence.ticket_shadow_schema import validate_relational_ticket_rows

RecoveryAction = Literal["inspect", "remove-expired", "repair-projection", "release-lease"]


@dataclass(frozen=True)
class ProjectionIssue:
    ticket_id: str
    repairable: bool
    reason: str


@dataclass(frozen=True)
class CapacityReport:
    retained_count: int
    principal_counts: dict[str, int]
    active_lease_ids: tuple[str, ...]
    expired_lease_ids: tuple[str, ...]
    projection_issues: tuple[ProjectionIssue, ...]
    changed_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def recover_ticket_capacity(
    database_url: str,
    *,
    action: RecoveryAction = "inspect",
    operator: str | None = None,
    reason: str | None = None,
    lease_id: UUID | None = None,
    api_drained: bool = False,
) -> CapacityReport:
    """Inspect or perform one tightly scoped, transactionally audited repair."""
    if action != "inspect" and (not operator or not reason):
        raise ValueError("Mutations require a non-empty operator and reason.")
    if (operator and len(operator) > 200) or (reason and len(reason) > 1000):
        raise ValueError("Operator or reason exceeds the bounded audit length.")
    if action == "release-lease" and (lease_id is None or not api_drained):
        raise ValueError("Lease release requires a lease ID and drained-system confirmation.")
    engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text(RESOURCE_LEASE_SCHEMA_SQL))
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('coeus:tickets'))"))
        before = _inspect(connection)
        changed_ids: tuple[str, ...] = ()
        event_type: str | None = None
        if action == "remove-expired":
            changed_ids = _remove_expired(connection)
            event_type = "ticket_capacity_expired_leases_recovered"
        elif action == "repair-projection":
            changed_ids = _repair_projection(connection, before)
            event_type = "ticket_capacity_projection_repaired"
        elif action == "release-lease":
            assert lease_id is not None
            changed_ids = _release_active_lease(connection, lease_id)
            event_type = "ticket_capacity_active_lease_force_released"
        if event_type and changed_ids:
            _append_audit(connection, event_type, operator or "", reason or "", changed_ids)
        after = _inspect(connection)
        return replace(after, changed_count=len(changed_ids))


def _inspect(connection: Connection) -> CapacityReport:
    retained_count = int(
        connection.execute(
            text("SELECT count(*) FROM coeus_ticket_aggregates WHERE consumes_capacity")
        ).scalar_one()
    )
    principals = connection.execute(
        text(
            "SELECT requester_user_id::text, count(*) FROM coeus_ticket_aggregates "
            "WHERE consumes_capacity GROUP BY requester_user_id ORDER BY requester_user_id"
        )
    ).all()
    leases = connection.execute(
        text(
            "SELECT lease_id::text, expires_at <= transaction_timestamp() AS expired "
            "FROM coeus_resource_leases WHERE resource_type = 'ticket_creation' "
            "ORDER BY lease_id"
        )
    ).all()
    active = tuple(row[0] for row in leases if not row[1])
    expired = tuple(row[0] for row in leases if row[1])
    return CapacityReport(
        retained_count=retained_count,
        principal_counts={row[0]: int(row[1]) for row in principals},
        active_lease_ids=active,
        expired_lease_ids=expired,
        projection_issues=_projection_issues(connection),
    )


def _projection_issues(connection: Connection) -> tuple[ProjectionIssue, ...]:
    rows = connection.execute(
        text(
            "SELECT ticket_id::text, requester_user_id::text, state, consumes_capacity, "
            "payload, canonical_hash FROM coeus_ticket_aggregates ORDER BY ticket_id"
        )
    ).mappings()
    issues: list[ProjectionIssue] = []
    for row in rows:
        payload = dict(row["payload"])
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if sha256(canonical.encode()).hexdigest() != row["canonical_hash"]:
            issues.append(ProjectionIssue(row["ticket_id"], False, "canonical hash mismatch"))
            continue
        try:
            ticket = decode_value(payload)
        except (TypeError, ValueError, KeyError):
            issues.append(ProjectionIssue(row["ticket_id"], False, "invalid ticket payload"))
            continue
        if not isinstance(ticket, TicketRecord) or str(ticket.ticket_id) != row["ticket_id"]:
            issues.append(ProjectionIssue(row["ticket_id"], False, "aggregate identity mismatch"))
            continue
        expected = (
            str(ticket.requester_user_id),
            ticket.state.value,
            ticket_consumes_capacity(ticket.state),
        )
        actual = (row["requester_user_id"], row["state"], row["consumes_capacity"])
        if actual != expected:
            issues.append(ProjectionIssue(row["ticket_id"], True, "derived projection drift"))
    return tuple(issues)


def _remove_expired(connection: Connection) -> tuple[str, ...]:
    return tuple(
        str(row[0])
        for row in connection.execute(
            text(
                "DELETE FROM coeus_resource_leases WHERE resource_type = 'ticket_creation' "
                "AND expires_at <= transaction_timestamp() RETURNING lease_id"
            )
        ).all()
    )


def _repair_projection(connection: Connection, report: CapacityReport) -> tuple[str, ...]:
    blockers = tuple(issue for issue in report.projection_issues if not issue.repairable)
    if blockers:
        raise RuntimeError("Non-repairable ticket aggregates block projection recovery.")
    repaired: list[str] = []
    for issue in report.projection_issues:
        row = connection.execute(
            text("SELECT payload FROM coeus_ticket_aggregates WHERE ticket_id = CAST(:id AS uuid)"),
            {"id": issue.ticket_id},
        ).scalar_one()
        ticket = decode_value(dict(row))
        assert isinstance(ticket, TicketRecord)
        connection.execute(
            text(
                "UPDATE coeus_ticket_aggregates SET requester_user_id=:requester, state=:state, "
                "consumes_capacity=:consumes WHERE ticket_id=CAST(:id AS uuid)"
            ),
            {
                "id": issue.ticket_id,
                "requester": ticket.requester_user_id,
                "state": ticket.state.value,
                "consumes": ticket_consumes_capacity(ticket.state),
            },
        )
        repaired.append(issue.ticket_id)
    validate_relational_ticket_rows(connection)
    return tuple(repaired)


def _release_active_lease(connection: Connection, lease_id: UUID) -> tuple[str, ...]:
    row = connection.execute(
        text(
            "SELECT resource_type, expires_at > transaction_timestamp() AS active "
            "FROM coeus_resource_leases WHERE lease_id=:lease_id FOR UPDATE"
        ),
        {"lease_id": lease_id},
    ).one_or_none()
    if row is None or row.resource_type != "ticket_creation" or not row.active:
        raise ValueError("The named lease is not an active ticket-creation lease.")
    connection.execute(
        text("DELETE FROM coeus_resource_leases WHERE lease_id=:lease_id"),
        {"lease_id": lease_id},
    )
    return (str(lease_id),)


def _append_audit(
    connection: Connection,
    event_type: str,
    operator: str,
    reason: str,
    changed_ids: tuple[str, ...],
) -> None:
    connection.execute(text(AUDIT_TABLE_SQL))
    connection.execute(text(AUDIT_ORDER_INDEX_SQL))
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events("
            "event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:event_id,:event_type,:occurred_at,:operator,CAST(:metadata AS jsonb))"
        ),
        {
            "event_id": uuid4(),
            "event_type": event_type,
            "occurred_at": datetime.now(UTC),
            "operator": operator,
            "metadata": json.dumps(
                {"reason": reason, "changedCount": len(changed_ids), "changedIds": changed_ids}
            ),
        },
    )
