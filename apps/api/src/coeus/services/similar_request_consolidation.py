"""Transactional manager controls for confirmed duplicate requests."""

from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import TicketRecord
from coeus.services.audit import AuditLog
from coeus.services.embeddings import EmbeddingService
from coeus.services.similar_request_scoring import (
    MANAGER_SIMILARITY_THRESHOLD,
    OPEN_SIMILARITY_STATES,
    ROUTING_READ_PERMISSIONS,
    score_similar_requests,
)
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices


def mark_duplicate_ticket(
    tickets: TicketServices,
    audit_log: AuditLog,
    embeddings: EmbeddingService,
    actor: UserAccount,
    ticket_id: UUID,
    related_ticket_id: UUID,
    *,
    withdraw_source: bool,
    similarity_verified: bool = False,
) -> TicketRecord:
    if Permission.TICKET_CONSOLIDATE not in actor.permissions:
        raise AppError(403, "permission_denied", "Permission is required for this action.")
    source = tickets.tickets.get_workflow_ticket(actor, ticket_id, ROUTING_READ_PERMISSIONS)
    related = tickets.tickets.get_workflow_ticket(
        actor, related_ticket_id, ROUTING_READ_PERMISSIONS
    )
    _validate_pair(source, related)
    already_marked = source.duplicate_of_ticket_id == related.ticket_id
    if already_marked and (not withdraw_source or source.state == TicketState.CANCELLED):
        _audit(audit_log, actor, source, related, withdraw_source, already_marked=True)
        return source
    if source.state not in OPEN_SIMILARITY_STATES or related.state not in OPEN_SIMILARITY_STATES:
        raise AppError(409, "invalid_ticket_state", "Only active tickets can be consolidated.")
    if not similarity_verified:
        matches = score_similar_requests(
            source,
            (related,),
            embeddings,
            MANAGER_SIMILARITY_THRESHOLD,
            actor.user_id,
        )
        if not matches:
            raise AppError(422, "duplicate_match_required", "The selected ticket is not a match.")
    if withdraw_source and _withdrawal_blocked(source):
        raise AppError(
            409,
            "duplicate_withdrawal_blocked",
            "This ticket cannot be withdrawn after a product has been released.",
        )
    source_linked = _related_link(source, related, actor)
    source_proposed = replace(
        source_linked,
        duplicate_of_ticket_id=related.ticket_id,
        state=TicketState.CANCELLED if withdraw_source else source.state,
        timeline=(
            *source_linked.timeline,
            timeline(
                source.ticket_id,
                actor.user_id,
                "duplicate_marked",
                f"Marked as a duplicate of {related.reference}"
                + (" and withdrawn." if withdraw_source else "."),
            ),
        ),
    )
    related_proposed = _related_link(related, source, actor)
    source_updated, _ = tickets.mutations.save_pair_audited(
        (source, related),
        (source_proposed, related_proposed),
        "ticket_duplicate_marked",
        actor,
        _metadata(source, related, withdraw_source, already_marked=False),
    )
    return source_updated


def _validate_pair(source: TicketRecord, related: TicketRecord) -> None:
    if source.ticket_id == related.ticket_id:
        raise AppError(422, "related_ticket_invalid", "A ticket cannot duplicate itself.")
    if source.duplicate_of_ticket_id not in {None, related.ticket_id}:
        raise AppError(
            409,
            "duplicate_target_conflict",
            "This ticket has another duplicate target.",
        )


def _withdrawal_blocked(ticket: TicketRecord) -> bool:
    return bool(
        not can_transition(ticket.state, TicketState.CANCELLED)
        or ticket.disseminations
        or ticket.product_index_records
    )


def _related_link(target: TicketRecord, related: TicketRecord, actor: UserAccount) -> TicketRecord:
    related_ids = (
        target.related_ticket_ids
        if related.ticket_id in target.related_ticket_ids
        else (*target.related_ticket_ids, related.ticket_id)
    )
    return replace(
        target,
        related_ticket_ids=related_ids,
        timeline=(
            *target.timeline,
            timeline(
                target.ticket_id,
                actor.user_id,
                "related_ticket_linked",
                f"Linked as related to {related.reference}.",
            ),
        ),
    )


def _audit(
    audit_log: AuditLog,
    actor: UserAccount,
    source: TicketRecord,
    related: TicketRecord,
    withdraw_source: bool,
    *,
    already_marked: bool,
) -> None:
    audit_log.record(
        "ticket_duplicate_marked",
        str(actor.user_id),
        _metadata(source, related, withdraw_source, already_marked),
    )


def _metadata(
    source: TicketRecord,
    related: TicketRecord,
    withdraw_source: bool,
    already_marked: bool,
) -> dict[str, str]:
    return {
        "ticket_id": str(source.ticket_id),
        "related_ticket_id": str(related.ticket_id),
        "withdraw_source": str(withdraw_source).lower(),
        "already_marked": str(already_marked).lower(),
    }
