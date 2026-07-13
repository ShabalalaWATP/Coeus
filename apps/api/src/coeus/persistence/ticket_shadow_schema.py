"""Schema bootstrap and reconciliation for versioned ticket shadow rows."""

import json
from hashlib import sha256
from typing import Any

from sqlalchemy import text

from coeus.persistence.draft_audience_projection import ensure_draft_audience_schema


def ensure_ticket_shadow_schema(connection: Any) -> None:
    ensure_draft_audience_schema(connection)
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS coeus_ticket_aggregates (
                ticket_id uuid PRIMARY KEY,
                version bigint NOT NULL CHECK (version > 0),
                payload jsonb NOT NULL,
                canonical_hash text NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS coeus_outbox (
                event_id uuid PRIMARY KEY,
                aggregate_id uuid NOT NULL,
                aggregate_version bigint NOT NULL,
                event_type text NOT NULL,
                payload jsonb NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                delivered_at timestamptz,
                UNIQUE (aggregate_id, aggregate_version, event_type)
            )
            """
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_coeus_outbox_pending "
            "ON coeus_outbox(created_at, event_id) WHERE delivered_at IS NULL"
        )
    )


def validate_ticket_shadow(engine: Any, payload: dict[str, Any]) -> None:
    expected: dict[str, str] = {}
    tickets = payload.get("tickets", [])
    for ticket in tickets if isinstance(tickets, list) else []:
        try:
            ticket_id = ticket["fields"]["ticket_id"]["__uuid__"]
        except (KeyError, TypeError):
            continue
        canonical = json.dumps(ticket, sort_keys=True, separators=(",", ":"))
        expected[ticket_id] = sha256(canonical.encode("utf-8")).hexdigest()
    with engine.connect() as connection:
        actual = dict(
            connection.execute(
                text("SELECT ticket_id::text, canonical_hash FROM coeus_ticket_aggregates")
            ).all()
        )
    if actual != expected:
        raise RuntimeError("Ticket shadow reconciliation failed; relational cutover is unsafe.")
