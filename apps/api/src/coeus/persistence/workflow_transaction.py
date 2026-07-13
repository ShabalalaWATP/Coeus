"""PostgreSQL transaction owner for QC release state and side-effect intent."""

import json
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from coeus.domain.store import StoreProduct
from coeus.domain.tickets import TicketRecord
from coeus.domain.workflow_transaction import ReleaseNotificationIntent, WorkflowAuditIntent
from coeus.persistence.audit_store import AUDIT_TABLE_SQL
from coeus.persistence.codec import encode_value
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.relational_schema import ensure_relational_schema
from coeus.persistence.state_store import (
    _encoded_ticket_hash,
    _encoded_ticket_id,
    _shadow_ticket_payload,
)
from coeus.persistence.store_projection_write import existing_embedding_hashes, save_product
from coeus.persistence.ticket_shadow_schema import ensure_ticket_shadow_schema


class PostgresWorkflowTransaction:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)

    def commit_ticket_create(
        self,
        ticket: TicketRecord,
        audit: WorkflowAuditIntent,
    ) -> bool:
        payload = encode_value(ticket)
        ticket_id = _encoded_ticket_id(payload)
        with self._engine.begin() as connection:
            self._prepare(connection)
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:ticket_id, 0))"),
                {"ticket_id": ticket_id},
            )
            exists = connection.execute(
                text(
                    "SELECT 1 FROM coeus_ticket_aggregates "
                    "WHERE ticket_id = CAST(:ticket_id AS uuid)"
                ),
                {"ticket_id": ticket_id},
            ).scalar_one_or_none()
            if exists is not None:
                return False
            self._write_ticket(connection, payload, ticket_id)
            self._append_audit(connection, audit)
        return True

    def commit_ticket_update(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audit: WorkflowAuditIntent,
    ) -> bool:
        expected_payload = encode_value(expected)
        updated_payload = encode_value(updated)
        with self._engine.begin() as connection:
            self._prepare(connection)
            ticket_id = self._lock_current(connection, expected_payload)
            if ticket_id is None:
                return False
            self._write_ticket(connection, updated_payload, ticket_id)
            self._append_audit(connection, audit)
        return True

    def commit_qc_release(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        product: StoreProduct,
        audit: WorkflowAuditIntent,
        notification: ReleaseNotificationIntent | None,
    ) -> bool:
        expected_payload = encode_value(expected)
        updated_payload = encode_value(updated)
        with self._engine.begin() as connection:
            self._prepare(connection)
            ticket_id = self._lock_current(connection, expected_payload)
            if ticket_id is None:
                return False
            hashes = existing_embedding_hashes(connection, (product.product_id,))
            save_product(connection, product, None, hashes)
            version = self._write_ticket(connection, updated_payload, ticket_id)
            self._append_audit(connection, audit)
            if notification is not None:
                self._append_notification(connection, expected.ticket_id, version, notification)
        return True

    @staticmethod
    def _prepare(connection: Connection) -> None:
        ensure_relational_schema(connection)
        ensure_ticket_shadow_schema(connection)
        connection.execute(text(AUDIT_TABLE_SQL))

    @staticmethod
    def _lock_current(connection: Connection, expected_payload: dict[str, object]) -> str | None:
        ticket_id = _encoded_ticket_id(expected_payload)
        current_hash = connection.execute(
            text(
                "SELECT canonical_hash FROM coeus_ticket_aggregates "
                "WHERE ticket_id = CAST(:ticket_id AS uuid) FOR UPDATE"
            ),
            {"ticket_id": ticket_id},
        ).scalar_one_or_none()
        return ticket_id if current_hash == _encoded_ticket_hash(expected_payload) else None

    @staticmethod
    def _write_ticket(
        connection: Connection, updated_payload: dict[str, object], ticket_id: str
    ) -> int:
        _shadow_ticket_payload(connection, {"tickets": [updated_payload]}, reconcile=False)
        return int(
            connection.execute(
                text(
                    "SELECT version FROM coeus_ticket_aggregates "
                    "WHERE ticket_id = CAST(:ticket_id AS uuid)"
                ),
                {"ticket_id": ticket_id},
            ).scalar_one()
        )

    @staticmethod
    def _append_audit(connection: Connection, audit: WorkflowAuditIntent) -> None:
        connection.execute(
            text(
                """
                INSERT INTO coeus_audit_events(
                  event_id, event_type, occurred_at, actor_user_id, metadata
                ) VALUES (
                  :event_id, :event_type, :occurred_at, :actor_user_id, CAST(:metadata AS jsonb)
                )
                """
            ),
            {
                "event_id": uuid4(),
                "event_type": audit.event_type,
                "occurred_at": datetime.now(UTC),
                "actor_user_id": str(audit.actor_user_id),
                "metadata": json.dumps(audit.metadata),
            },
        )

    @staticmethod
    def _append_notification(
        connection: Connection,
        ticket_id: UUID,
        version: int,
        notification: ReleaseNotificationIntent,
    ) -> None:
        event_type = "product_release_notification"
        event_id = uuid5(NAMESPACE_URL, f"coeus:{ticket_id}:{version}:{event_type}")
        connection.execute(
            text(
                """
                INSERT INTO coeus_outbox(
                  event_id, aggregate_id, aggregate_version, event_type, payload
                ) VALUES (
                  :event_id, :ticket_id, :version, :event_type, CAST(:payload AS jsonb)
                )
                ON CONFLICT (aggregate_id, aggregate_version, event_type) DO NOTHING
                """
            ),
            {
                "event_id": event_id,
                "ticket_id": ticket_id,
                "version": version,
                "event_type": event_type,
                "payload": json.dumps(
                    {
                        "requester_user_id": str(notification.requester_user_id),
                        "ticket_reference": notification.ticket_reference,
                        "product_id": str(notification.product_id),
                        "product_reference": notification.product_reference,
                        "product_title": notification.product_title,
                    }
                ),
            },
        )
