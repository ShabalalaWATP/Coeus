"""Audit and outbox writes shared by PostgreSQL workflow transactions."""

import json
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.workflow_transaction import (
    ReleaseNotificationIntent,
    WorkflowAuditIntent,
    WorkflowOutboxIntent,
)


class WorkflowTransactionWrites:
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
                "metadata": json.dumps(dict(audit.metadata)),
            },
        )

    @classmethod
    def _append_audits(
        cls, connection: Connection, audits: tuple[WorkflowAuditIntent, ...]
    ) -> None:
        for audit in audits:
            cls._append_audit(connection, audit)

    @classmethod
    def _append_outbox_intents(
        cls,
        connection: Connection,
        ticket_id: UUID,
        version: int,
        intents: tuple[WorkflowOutboxIntent, ...],
    ) -> None:
        for intent in intents:
            cls._append_outbox(connection, ticket_id, version, intent)

    @staticmethod
    def _append_outbox(
        connection: Connection,
        ticket_id: UUID,
        version: int,
        intent: WorkflowOutboxIntent,
    ) -> None:
        event_id = uuid5(NAMESPACE_URL, f"coeus:{ticket_id}:{version}:{intent.event_type}")
        payload = dict(intent.payload)
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
                "event_type": intent.event_type,
                "payload": json.dumps(payload),
            },
        )
        stored = (
            connection.execute(
                text(
                    """
                SELECT event_id, payload FROM coeus_outbox
                WHERE aggregate_id = :ticket_id
                  AND aggregate_version = :version
                  AND event_type = :event_type
                """
                ),
                {"ticket_id": ticket_id, "version": version, "event_type": intent.event_type},
            )
            .mappings()
            .one()
        )
        if stored["event_id"] != event_id or dict(stored["payload"]) != payload:
            raise RuntimeError("Conflicting workflow outbox intent already exists.")

    @staticmethod
    def _append_notification(
        connection: Connection,
        ticket_id: UUID,
        version: int,
        notification: ReleaseNotificationIntent,
    ) -> None:
        event_type = "product_release_notification"
        event_id = uuid5(NAMESPACE_URL, f"coeus:{ticket_id}:{version}:{event_type}")
        payload = {
            "requester_user_id": str(notification.requester_user_id),
            "ticket_reference": notification.ticket_reference,
            "product_id": str(notification.product_id),
            "product_reference": notification.product_reference,
            "product_title": notification.product_title,
        }
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
                "payload": json.dumps(payload),
            },
        )
        stored = (
            connection.execute(
                text(
                    """
                SELECT event_id, payload
                FROM coeus_outbox
                WHERE aggregate_id = :ticket_id
                  AND aggregate_version = :version
                  AND event_type = :event_type
                """
                ),
                {"ticket_id": ticket_id, "version": version, "event_type": event_type},
            )
            .mappings()
            .one()
        )
        if stored["event_id"] != event_id or dict(stored["payload"]) != payload:
            raise RuntimeError("Conflicting release notification intent already exists.")
