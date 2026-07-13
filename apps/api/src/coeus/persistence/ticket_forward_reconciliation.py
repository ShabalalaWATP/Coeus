"""Quiesced, audited reconciliation of N-1 legacy ticket writes."""

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from coeus.domain.tickets import TicketRecord
from coeus.persistence.audit_store import AUDIT_ORDER_INDEX_SQL, AUDIT_TABLE_SQL
from coeus.persistence.codec import decode_value
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.state_store import _save_ticket_counter, _shadow_ticket_payload
from coeus.persistence.ticket_rollback_checkpoint import (
    ROLLBACK_CHECKPOINT_FORMAT_VERSION,
    ROLLBACK_CHECKPOINT_NAMESPACE,
)
from coeus.persistence.ticket_shadow_schema import (
    ensure_ticket_shadow_schema,
    validate_relational_ticket_rows,
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ForwardReconciliationReport:
    ticket_count: int
    changed_count: int
    removed_count: int
    checkpoint_id: str


def reconcile_legacy_ticket_state(
    database_url: str,
    *,
    operator: str,
    reason: str,
) -> ForwardReconciliationReport:
    """Import quiesced N-1 writes only when the relational baseline is unchanged."""
    operator = operator.strip()
    reason = reason.strip()
    if not operator or not reason:
        raise ValueError("Forward reconciliation requires a non-empty operator and reason.")
    if len(operator) > 200 or len(reason) > 1000:
        raise ValueError("Operator or reason exceeds the bounded audit length.")
    engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            ensure_ticket_shadow_schema(connection)
            connection.execute(text(AUDIT_TABLE_SQL))
            connection.execute(text(AUDIT_ORDER_INDEX_SQL))
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('coeus:ticket-rollback'))")
            )
            checkpoint = connection.execute(
                text("SELECT payload FROM coeus_state WHERE namespace=:namespace FOR UPDATE"),
                {"namespace": ROLLBACK_CHECKPOINT_NAMESPACE},
            ).scalar_one_or_none()
            legacy = connection.execute(
                text("SELECT payload FROM coeus_state WHERE namespace='tickets' FOR UPDATE")
            ).scalar_one_or_none()
            checkpoint_id, baseline = _validated_checkpoint(checkpoint)
            payload, legacy_hashes, counter = _validated_legacy_payload(legacy)
            current: dict[str, str] = {
                str(row[0]): str(row[1])
                for row in connection.execute(
                    text(
                        "SELECT ticket_id::text, canonical_hash "
                        "FROM coeus_ticket_aggregates ORDER BY ticket_id FOR UPDATE"
                    )
                ).all()
            }
            if current != baseline:
                raise RuntimeError(
                    "Relational tickets changed after rollback projection; forward "
                    "reconciliation was not applied."
                )
            changed = sum(
                baseline.get(ticket_id) != digest for ticket_id, digest in legacy_hashes.items()
            )
            removed = len(set(baseline).difference(legacy_hashes))
            _shadow_ticket_payload(connection, payload)
            _save_ticket_counter(connection, counter)
            validate_relational_ticket_rows(connection)
            connection.execute(
                text(
                    """
                    INSERT INTO coeus_audit_events(
                      event_id, event_type, occurred_at, actor_user_id, metadata
                    ) VALUES (
                      :event_id, 'legacy_ticket_state_reconciled', now(), :operator,
                      CAST(:metadata AS jsonb)
                    )
                    """
                ),
                {
                    "event_id": uuid4(),
                    "operator": operator,
                    "metadata": json.dumps(
                        {
                            "checkpoint_id": checkpoint_id,
                            "ticket_count": len(legacy_hashes),
                            "changed_count": changed,
                            "removed_count": removed,
                            "reason": reason,
                        },
                        sort_keys=True,
                    ),
                },
            )
            connection.execute(
                text("DELETE FROM coeus_state WHERE namespace=:namespace"),
                {"namespace": ROLLBACK_CHECKPOINT_NAMESPACE},
            )
        return ForwardReconciliationReport(len(legacy_hashes), changed, removed, checkpoint_id)
    finally:
        engine.dispose()


def _validated_checkpoint(value: object) -> tuple[str, dict[str, str]]:
    if (
        not isinstance(value, dict)
        or value.get("format_version") != ROLLBACK_CHECKPOINT_FORMAT_VERSION
    ):
        raise RuntimeError("A valid ticket rollback checkpoint is required.")
    checkpoint_id = value.get("checkpoint_id")
    hashes = value.get("ticket_hashes")
    if not isinstance(checkpoint_id, str) or not checkpoint_id:
        raise RuntimeError("Ticket rollback checkpoint identity is invalid.")
    if not isinstance(hashes, dict):
        raise RuntimeError("Ticket rollback checkpoint hashes are invalid.")
    validated: dict[str, str] = {}
    for ticket_id, digest in hashes.items():
        try:
            UUID(str(ticket_id))
        except ValueError as exc:
            raise RuntimeError("Ticket rollback checkpoint contains an invalid ID.") from exc
        if not isinstance(digest, str) or _SHA256_PATTERN.fullmatch(digest) is None:
            raise RuntimeError("Ticket rollback checkpoint contains an invalid hash.")
        validated[str(ticket_id)] = digest
    return checkpoint_id, validated


def _validated_legacy_payload(
    value: object,
) -> tuple[dict[str, object], dict[str, str], int]:
    if not isinstance(value, dict):
        raise RuntimeError("Legacy ticket state is missing or invalid.")
    tickets = value.get("tickets")
    counter = value.get("counter")
    if not isinstance(tickets, list) or not isinstance(counter, int) or counter < 0:
        raise RuntimeError("Legacy ticket state shape is invalid.")
    hashes: dict[str, str] = {}
    for encoded in tickets:
        if not isinstance(encoded, dict):
            raise RuntimeError("Legacy ticket state contains an invalid aggregate.")
        try:
            decoded = decode_value(encoded)
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Legacy ticket state contains an invalid aggregate.") from exc
        if not isinstance(decoded, TicketRecord):
            raise RuntimeError("Legacy ticket state contains a non-ticket aggregate.")
        ticket_id = str(decoded.ticket_id)
        if ticket_id in hashes:
            raise RuntimeError("Legacy ticket state contains duplicate ticket IDs.")
        canonical = json.dumps(encoded, sort_keys=True, separators=(",", ":"))
        hashes[ticket_id] = sha256(canonical.encode("utf-8")).hexdigest()
    return {"counter": counter, "tickets": tickets}, hashes, counter
