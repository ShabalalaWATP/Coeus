"""Serializable backfill and reconciliation for relational draft audiences."""

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from coeus.domain.tickets import TicketRecord
from coeus.persistence.audit_store import AUDIT_ORDER_INDEX_SQL, AUDIT_TABLE_SQL
from coeus.persistence.codec import decode_value
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.draft_audience_projection import (
    ensure_draft_audience_schema,
    ticket_draft_audience_relationships,
)
from coeus.persistence.ticket_shadow_schema import validate_relational_ticket_rows


@dataclass(frozen=True, order=True)
class AudienceRelationship:
    product_id: str
    principal_id: str
    reason: str
    ticket_id: str


@dataclass(frozen=True)
class AudienceReconciliationReport:
    expected_count: int
    actual_count: int
    missing: tuple[AudienceRelationship, ...]
    extra: tuple[AudienceRelationship, ...]
    changed_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def reconcile_draft_audiences(
    database_url: str,
    *,
    apply: bool = False,
    operator: str | None = None,
    reason: str | None = None,
) -> AudienceReconciliationReport:
    if apply and (not operator or not reason):
        raise ValueError("Applying reconciliation requires an operator and reason.")
    if (operator and len(operator) > 200) or (reason and len(reason) > 1000):
        raise ValueError("Operator or reason exceeds the bounded audit length.")
    engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
    with (
        engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection,
        connection.begin(),
    ):
        ensure_draft_audience_schema(connection)
        validate_relational_ticket_rows(connection)
        report = _report(connection)
        if not apply:
            return report
        changed = _apply(connection, report)
        after = _report(connection)
        if after.missing or after.extra:
            raise RuntimeError("Draft audience reconciliation did not converge.")
        if changed:
            _append_audit(connection, operator or "", reason or "", report, changed)
        return replace(after, changed_count=changed)


def _report(connection: Connection) -> AudienceReconciliationReport:
    expected: set[AudienceRelationship] = set()
    rows = connection.execute(
        text("SELECT ticket_id::text, payload FROM coeus_ticket_aggregates ORDER BY ticket_id")
    ).mappings()
    for row in rows:
        ticket = decode_value(dict(row["payload"]))
        if not isinstance(ticket, TicketRecord):
            raise RuntimeError("A ticket aggregate payload did not decode as a ticket.")
        expected.update(
            AudienceRelationship(str(product), str(principal), reason.value, row["ticket_id"])
            for product, principal, reason in ticket_draft_audience_relationships(ticket)
        )
    actual = {
        AudienceRelationship(*row)
        for row in connection.execute(
            text(
                "SELECT product_id::text, principal_id::text, reason, ticket_id::text "
                "FROM coeus_draft_audiences ORDER BY product_id, principal_id, reason, ticket_id"
            )
        ).all()
    }
    return AudienceReconciliationReport(
        expected_count=len(expected),
        actual_count=len(actual),
        missing=tuple(sorted(expected - actual)),
        extra=tuple(sorted(actual - expected)),
    )


def _apply(connection: Connection, report: AudienceReconciliationReport) -> int:
    for relationship in report.extra:
        connection.execute(
            text(
                "DELETE FROM coeus_draft_audiences WHERE product_id=CAST(:product AS uuid) "
                "AND principal_id=CAST(:principal AS uuid) AND reason=:reason "
                "AND ticket_id=CAST(:ticket AS uuid)"
            ),
            _parameters(relationship),
        )
    for relationship in report.missing:
        connection.execute(
            text(
                "INSERT INTO coeus_draft_audiences(product_id,principal_id,reason,ticket_id) "
                "VALUES (CAST(:product AS uuid),CAST(:principal AS uuid),:reason,"
                "CAST(:ticket AS uuid)) ON CONFLICT DO NOTHING"
            ),
            _parameters(relationship),
        )
    return len(report.extra) + len(report.missing)


def _parameters(relationship: AudienceRelationship) -> dict[str, str]:
    return {
        "product": relationship.product_id,
        "principal": relationship.principal_id,
        "reason": relationship.reason,
        "ticket": relationship.ticket_id,
    }


def _append_audit(
    connection: Connection,
    operator: str,
    reason: str,
    report: AudienceReconciliationReport,
    changed: int,
) -> None:
    connection.execute(text(AUDIT_TABLE_SQL))
    connection.execute(text(AUDIT_ORDER_INDEX_SQL))
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events("
            "event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:id,'draft_audience_reconciled',:occurred,:operator,CAST(:metadata AS jsonb))"
        ),
        {
            "id": uuid4(),
            "occurred": datetime.now(UTC),
            "operator": operator,
            "metadata": json.dumps(
                {
                    "reason": reason,
                    "missingCount": len(report.missing),
                    "extraCount": len(report.extra),
                    "changedCount": changed,
                }
            ),
        },
    )
