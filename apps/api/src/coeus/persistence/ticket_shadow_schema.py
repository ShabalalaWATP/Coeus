"""Schema bootstrap and reconciliation for versioned ticket shadow rows."""

import json
from hashlib import sha256
from typing import Any

from sqlalchemy import text

from coeus.domain.ticket_retention import ticket_consumes_capacity
from coeus.domain.tickets import TicketRecord
from coeus.persistence.codec import decode_value
from coeus.persistence.draft_audience_projection import ensure_draft_audience_schema


def ensure_ticket_shadow_schema(connection: Any) -> None:
    ensure_draft_audience_schema(connection)
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS coeus_ticket_aggregates (
                ticket_id uuid PRIMARY KEY,
                requester_user_id uuid NOT NULL,
                state text NOT NULL,
                consumes_capacity boolean NOT NULL,
                version bigint NOT NULL CHECK (version > 0),
                payload jsonb NOT NULL,
                canonical_hash text NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    )
    connection.execute(
        text("ALTER TABLE coeus_ticket_aggregates ADD COLUMN IF NOT EXISTS requester_user_id uuid")
    )
    connection.execute(
        text("ALTER TABLE coeus_ticket_aggregates ADD COLUMN IF NOT EXISTS state text")
    )
    connection.execute(
        text(
            "ALTER TABLE coeus_ticket_aggregates ADD COLUMN IF NOT EXISTS consumes_capacity boolean"
        )
    )
    connection.execute(
        text(
            """
            UPDATE coeus_ticket_aggregates SET
              requester_user_id = (payload -> 'fields' -> 'requester_user_id' ->> '__uuid__')::uuid,
              state = payload -> 'fields' -> 'state' ->> 'value',
              consumes_capacity = payload -> 'fields' -> 'state' ->> 'value'
                NOT IN ('CANCELLED', 'CLOSED_DELIVERED', 'CLOSED_EXISTING_PRODUCT_ACCEPTED')
            WHERE requester_user_id IS NULL OR state IS NULL OR consumes_capacity IS NULL
            """
        )
    )
    connection.execute(
        text("ALTER TABLE coeus_ticket_aggregates ALTER COLUMN requester_user_id SET NOT NULL")
    )
    connection.execute(text("ALTER TABLE coeus_ticket_aggregates ALTER COLUMN state SET NOT NULL"))
    connection.execute(
        text("ALTER TABLE coeus_ticket_aggregates ALTER COLUMN consumes_capacity SET NOT NULL")
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_coeus_ticket_capacity "
            "ON coeus_ticket_aggregates(requester_user_id) WHERE consumes_capacity"
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
                available_at timestamptz NOT NULL DEFAULT now(),
                attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
                claimed_by uuid,
                claim_expires_at timestamptz,
                last_error text,
                delivered_at timestamptz,
                dead_lettered_at timestamptz,
                UNIQUE (aggregate_id, aggregate_version, event_type)
            )
            """
        )
    )
    connection.execute(
        text(
            "ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS "
            "available_at timestamptz NOT NULL DEFAULT now()"
        )
    )
    connection.execute(
        text(
            "ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS "
            "attempt_count integer NOT NULL DEFAULT 0"
        )
    )
    connection.execute(text("ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS claimed_by uuid"))
    connection.execute(
        text("ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS claim_expires_at timestamptz")
    )
    connection.execute(text("ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS last_error text"))
    connection.execute(
        text("ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS dead_lettered_at timestamptz")
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_coeus_outbox_pending "
            "ON coeus_outbox(available_at, created_at, event_id) "
            "WHERE delivered_at IS NULL AND dead_lettered_at IS NULL"
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


def validate_relational_ticket_rows(connection: Any) -> None:
    """Fail startup when an aggregate or its admission projection is inconsistent."""
    rows = connection.execute(
        text(
            "SELECT ticket_id::text, requester_user_id::text, state, consumes_capacity, "
            "payload, canonical_hash FROM coeus_ticket_aggregates ORDER BY ticket_id"
        )
    ).mappings()
    for row in rows:
        payload = dict(row["payload"])
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        ticket = decode_value(payload)
        valid = (
            isinstance(ticket, TicketRecord)
            and str(ticket.ticket_id) == row["ticket_id"]
            and str(ticket.requester_user_id) == row["requester_user_id"]
            and ticket.state.value == row["state"]
            and ticket_consumes_capacity(ticket.state) is row["consumes_capacity"]
            and sha256(canonical.encode("utf-8")).hexdigest() == row["canonical_hash"]
        )
        if not valid:
            raise RuntimeError(
                "Ticket aggregate reconciliation failed; relational cutover is unsafe."
            )
