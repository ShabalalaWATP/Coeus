from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import TicketRecord
from coeus.persistence.search_index_repository import SearchIndexRepository
from coeus.services.audit import AuditLog
from coeus.services.embeddings import EmbeddingService
from coeus.services.rfi_ranking import query_text
from coeus.services.search_configuration import SearchConfigurationService
from coeus.services.search_embeddings import SearchEmbeddingService
from coeus.services.search_generation import semantic_generation_usable
from coeus.services.similar_request_consolidation import mark_duplicate_ticket
from coeus.services.similar_request_scoring import (
    CUSTOMER_SIMILARITY_THRESHOLD,
    MANAGER_SIMILARITY_THRESHOLD,
    OPEN_SIMILARITY_STATES,
    ROUTING_READ_PERMISSIONS,
    SimilarRequestMatch,
    score_similar_requests,
)
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

CUSTOMER_NOTICE_STATES = OPEN_SIMILARITY_STATES - {TicketState.INFO_REQUIRED}


class SimilarRequestService:
    """Coordinates customer notices and manager links for similar open tickets."""

    def __init__(
        self,
        tickets: TicketServices,
        audit_log: AuditLog,
        embeddings: EmbeddingService,
        search_index: SearchIndexRepository | None = None,
        search_configuration: SearchConfigurationService | None = None,
        search_embeddings: SearchEmbeddingService | None = None,
    ) -> None:
        self._tickets = tickets
        self._audit_log = audit_log
        self._embeddings = embeddings
        self._search_index = search_index
        self._search_configuration = search_configuration
        self._search_embeddings = search_embeddings

    def customer_notice(
        self, actor: UserAccount, ticket_id: UUID
    ) -> tuple[SimilarRequestMatch, ...]:
        # Object-level check: the querying customer must be able to read the source ticket.
        source = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        # Only run for submitted, non-editable tickets. Draft or info-required tickets keep
        # their intake editable, which would let a customer replay the check as a probe. In
        # those states there is no notice to give, so return without scoring.
        if source.state not in CUSTOMER_NOTICE_STATES:
            return ()
        # Customers only ever see matches they already have need-to-know for. Hidden overlaps
        # are the manager panel's job to catch; nothing derived from invisible tickets (counts,
        # booleans, audit fields) is computed or returned on the customer path.
        candidates = self._bounded_candidates(
            source,
            self._tickets.tickets.list_visible_tickets(actor),
        )
        visible = tuple(
            match
            for match in self._score(
                source, candidates, CUSTOMER_SIMILARITY_THRESHOLD, actor.user_id
            )
            if self._customer_can_see(actor, match.ticket_id)
        )
        if visible:
            self._audit_log.record(
                "similar_request_notified",
                str(actor.user_id),
                {
                    "ticket_id": str(source.ticket_id),
                    "visible_match_ids": ",".join(str(match.ticket_id) for match in visible),
                },
            )
        return visible

    def manager_matches(
        self, actor: UserAccount, ticket_id: UUID
    ) -> tuple[SimilarRequestMatch, ...]:
        source = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ROUTING_READ_PERMISSIONS
        )
        candidates = self._bounded_candidates(
            source,
            self._tickets.tickets.list_workflow_tickets(actor, ROUTING_READ_PERMISSIONS),
        )
        return self._score(source, candidates, MANAGER_SIMILARITY_THRESHOLD, actor.user_id)

    def manager_match(
        self, actor: UserAccount, ticket_id: UUID, related_ticket_id: UUID
    ) -> SimilarRequestMatch | None:
        """Return one authorised pair result without rescanning the ticket corpus."""
        source = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ROUTING_READ_PERMISSIONS
        )
        related = self._tickets.tickets.get_workflow_ticket(
            actor, related_ticket_id, ROUTING_READ_PERMISSIONS
        )
        return self._find_match(source, related, MANAGER_SIMILARITY_THRESHOLD, actor.user_id)

    def link_related(
        self, actor: UserAccount, ticket_id: UUID, related_ticket_id: UUID
    ) -> TicketRecord:
        source = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ROUTING_READ_PERMISSIONS
        )
        related = self._tickets.tickets.get_workflow_ticket(
            actor, related_ticket_id, ROUTING_READ_PERMISSIONS
        )
        if source.ticket_id == related.ticket_id:
            raise AppError(422, "related_ticket_invalid", "A ticket cannot link to itself.")
        if not self._is_open(source) or not self._is_open(related):
            raise AppError(409, "invalid_ticket_state", "Only open tickets can be linked.")
        already = related.ticket_id in source.related_ticket_ids
        if already:
            self._audit_link(actor, source, related, already_linked=True)
            return source
        source_proposed = self._related_link(source, related, actor)
        related_proposed = self._related_link(related, source, actor)
        source_updated, _related_updated = self._tickets.mutations.save_pair_audited(
            (source, related),
            (source_proposed, related_proposed),
            "tickets_linked",
            actor,
            {
                "ticket_id": str(source.ticket_id),
                "related_ticket_id": str(related.ticket_id),
                "already_linked": "false",
            },
        )
        return source_updated

    def mark_duplicate(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        related_ticket_id: UUID,
        *,
        withdraw_source: bool,
    ) -> TicketRecord:
        if Permission.TICKET_CONSOLIDATE not in actor.permissions:
            raise AppError(403, "permission_denied", "Permission is required for this action.")
        if self.manager_match(actor, ticket_id, related_ticket_id) is None:
            raise AppError(422, "duplicate_match_required", "The selected ticket is not a match.")
        return mark_duplicate_ticket(
            self._tickets,
            self._audit_log,
            self._embeddings,
            actor,
            ticket_id,
            related_ticket_id,
            withdraw_source=withdraw_source,
            similarity_verified=True,
        )

    def _score(
        self,
        source: TicketRecord,
        candidates: tuple[TicketRecord, ...],
        threshold: float,
        principal_id: UUID,
    ) -> tuple[SimilarRequestMatch, ...]:
        semantic_rank = self._indexed_semantic_rank(source, candidates, principal_id)
        return score_similar_requests(
            source,
            candidates,
            self._embeddings,
            threshold,
            principal_id,
            semantic_rank_override=semantic_rank,
        )

    def _indexed_semantic_rank(
        self,
        source: TicketRecord,
        candidates: tuple[TicketRecord, ...],
        principal_id: UUID,
    ) -> dict[UUID, tuple[int, float]] | None:
        if (
            self._search_index is None
            or self._search_configuration is None
            or self._search_embeddings is None
        ):
            return None
        state = self._search_configuration.state()
        if not semantic_generation_usable(state.index_status, state.degraded_reason):
            return None
        query = query_text(source.intake)
        vector = self._search_embeddings.embed(
            query,
            purpose="query",
            principal_id=principal_id,
        )
        hits = self._search_index.search_tickets(
            query,
            vector,
            frozenset(ticket.ticket_id for ticket in candidates),
            frozenset(state.value for state in OPEN_SIMILARITY_STATES),
        )
        return {
            hit.ticket_id: (hit.vector_rank, hit.vector_score)
            for hit in hits
            if hit.vector_rank is not None
        }

    def _find_match(
        self,
        source: TicketRecord,
        related: TicketRecord,
        threshold: float,
        principal_id: UUID,
    ) -> SimilarRequestMatch | None:
        return next(iter(self._score(source, (related,), threshold, principal_id)), None)

    @staticmethod
    def _bounded_candidates(
        source: TicketRecord, candidates: tuple[TicketRecord, ...]
    ) -> tuple[TicketRecord, ...]:
        eligible = (
            ticket
            for ticket in candidates
            if ticket.ticket_id != source.ticket_id and ticket.state in OPEN_SIMILARITY_STATES
        )
        return tuple(eligible)

    def _customer_can_see(self, actor: UserAccount, ticket_id: UUID) -> bool:
        try:
            self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        except AppError:
            return False
        return True

    @staticmethod
    def _is_open(ticket: TicketRecord) -> bool:
        return ticket.state in OPEN_SIMILARITY_STATES

    @staticmethod
    def _related_link(
        target: TicketRecord, related: TicketRecord, actor: UserAccount
    ) -> TicketRecord:
        return replace(
            target,
            related_ticket_ids=_append_uuid(target.related_ticket_ids, related.ticket_id),
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

    def _audit_link(
        self,
        actor: UserAccount,
        source: TicketRecord,
        related: TicketRecord,
        *,
        already_linked: bool,
    ) -> None:
        self._audit_log.record(
            "tickets_linked",
            str(actor.user_id),
            {
                "ticket_id": str(source.ticket_id),
                "related_ticket_id": str(related.ticket_id),
                "already_linked": str(already_linked).lower(),
            },
        )


def _append_uuid(values: tuple[UUID, ...], value: UUID) -> tuple[UUID, ...]:
    return values if value in values else (*values, value)
