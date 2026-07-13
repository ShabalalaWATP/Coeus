"""Persist and query ticket-derived draft-product audience relationships."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import text

from coeus.domain.draft_audience import DraftAudienceReason
from coeus.domain.qc_assignment import active_qc_reviewer_id
from coeus.domain.tickets import TicketRecord
from coeus.persistence.codec import decode_value


class PostgresDraftAudienceProjection:
    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def reasons_for(self, product_id: UUID, principal_id: UUID) -> tuple[DraftAudienceReason, ...]:
        with self._engine.connect() as connection:
            reasons = connection.execute(
                text(
                    """
                    SELECT DISTINCT reason FROM coeus_draft_audiences
                    WHERE product_id = :product_id AND principal_id = :principal_id
                    ORDER BY reason
                    """
                ),
                {"product_id": product_id, "principal_id": principal_id},
            ).scalars()
            return tuple(DraftAudienceReason(reason) for reason in reasons)

    def contains(self, product_id: UUID, principal_id: UUID, reason: DraftAudienceReason) -> bool:
        with self._engine.connect() as connection:
            return bool(
                connection.execute(
                    text(
                        """
                        SELECT EXISTS(
                          SELECT 1 FROM coeus_draft_audiences
                          WHERE product_id = :product_id
                            AND principal_id = :principal_id
                            AND reason = :reason
                        )
                        """
                    ),
                    {
                        "product_id": product_id,
                        "principal_id": principal_id,
                        "reason": reason.value,
                    },
                ).scalar_one()
            )


class LocalDraftAudienceProjection:
    """Derive local-mode relationships from authoritative ticket snapshots."""

    def __init__(self, ticket_provider: Callable[[], tuple[TicketRecord, ...]]) -> None:
        self._ticket_provider = ticket_provider

    def reasons_for(self, product_id: UUID, principal_id: UUID) -> tuple[DraftAudienceReason, ...]:
        reasons = {
            reason
            for ticket in self._ticket_provider()
            for related_product_id, related_principal_id, reason in (
                ticket_draft_audience_relationships(ticket)
            )
            if related_product_id == product_id and related_principal_id == principal_id
        }
        return tuple(sorted(reasons))

    def contains(self, product_id: UUID, principal_id: UUID, reason: DraftAudienceReason) -> bool:
        return reason in self.reasons_for(product_id, principal_id)


def ensure_draft_audience_schema(connection: Any) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS coeus_draft_audiences (
                product_id uuid NOT NULL,
                principal_id uuid NOT NULL,
                reason text NOT NULL,
                ticket_id uuid NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY(product_id, principal_id, reason, ticket_id)
            )
            """
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_coeus_draft_audiences_principal "
            "ON coeus_draft_audiences(principal_id, product_id, reason)"
        )
    )


def sync_ticket_draft_audiences(connection: Any, encoded_ticket: dict[str, Any]) -> None:
    ticket = decode_value(encoded_ticket)
    if not isinstance(ticket, TicketRecord):
        return
    connection.execute(
        text("DELETE FROM coeus_draft_audiences WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket.ticket_id},
    )
    relationships = ticket_draft_audience_relationships(ticket)
    for product_id, principal_id, reason in relationships:
        connection.execute(
            text(
                """
                INSERT INTO coeus_draft_audiences(
                  product_id, principal_id, reason, ticket_id, updated_at
                ) VALUES (:product_id, :principal_id, :reason, :ticket_id, now())
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "product_id": product_id,
                "principal_id": principal_id,
                "reason": reason.value,
                "ticket_id": ticket.ticket_id,
            },
        )


def ticket_draft_audience_relationships(
    ticket: TicketRecord,
) -> set[tuple[UUID, UUID, DraftAudienceReason]]:
    """Derive indexed object relationships from one authoritative ticket."""
    relationships = {
        (link.product_id, assignment.analyst_user_id, DraftAudienceReason.ASSIGNED_ANALYST)
        for link in ticket.linked_products
        for assignment in ticket.analyst_assignments
        if assignment.active
    }
    relationships.update(
        (link.product_id, assignment.assigned_by_user_id, DraftAudienceReason.RESPONSIBLE_MANAGER)
        for link in ticket.linked_products
        for assignment in ticket.analyst_assignments
        if assignment.active
    )
    reviewer_id = active_qc_reviewer_id(ticket)
    if reviewer_id is not None:
        relationships.update(
            (link.product_id, reviewer_id, DraftAudienceReason.QUALITY_CONTROL)
            for link in ticket.linked_products
        )
    return relationships
