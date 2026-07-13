"""Verified reverse projection for relational ticket rollback."""

import json
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import create_engine, text

from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.ticket_rollback_checkpoint import (
    ROLLBACK_CHECKPOINT_FORMAT_VERSION,
    ROLLBACK_CHECKPOINT_NAMESPACE,
)


def reverse_project_ticket_state(database_url: str) -> int:
    """Write current relational aggregates to the legacy namespace atomically.

    Callers must quiesce ticket writers before invoking this operation. Every
    aggregate hash is verified before the legacy namespace is replaced.
    """
    engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT ticket_id::text, payload, canonical_hash "
                    "FROM coeus_ticket_aggregates "
                    "ORDER BY ticket_id FOR SHARE"
                )
            ).all()
            tickets = [dict(row.payload) for row in rows]
            for ticket, row in zip(tickets, rows, strict=True):
                canonical = json.dumps(ticket, sort_keys=True, separators=(",", ":"))
                if sha256(canonical.encode("utf-8")).hexdigest() != row.canonical_hash:
                    raise RuntimeError(
                        "Ticket reconciliation failed; legacy rollback namespace was not changed."
                    )
            counter = connection.execute(
                text(
                    "SELECT COALESCE((payload ->> 'counter')::bigint, 0) "
                    "FROM coeus_state WHERE namespace = 'ticket_meta'"
                )
            ).scalar_one_or_none()
            payload = {"counter": int(counter or 0), "tickets": tickets}
            checkpoint = {
                "format_version": ROLLBACK_CHECKPOINT_FORMAT_VERSION,
                "checkpoint_id": str(uuid4()),
                "ticket_hashes": {str(row.ticket_id): str(row.canonical_hash) for row in rows},
            }
            connection.execute(
                text(
                    """
                    INSERT INTO coeus_state(namespace, payload, updated_at)
                    VALUES ('tickets', CAST(:payload AS jsonb), now())
                    ON CONFLICT (namespace) DO UPDATE SET
                      payload = EXCLUDED.payload, updated_at = now()
                    """
                ),
                {"payload": json.dumps(payload)},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO coeus_state(namespace, payload, updated_at)
                    VALUES (:namespace, CAST(:payload AS jsonb), now())
                    ON CONFLICT (namespace) DO UPDATE SET
                      payload = EXCLUDED.payload, updated_at = now()
                    """
                ),
                {
                    "namespace": ROLLBACK_CHECKPOINT_NAMESPACE,
                    "payload": json.dumps(checkpoint),
                },
            )
        return len(tickets)
    finally:
        engine.dispose()
