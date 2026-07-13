from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.tickets import (
    CollaboratorAccess,
    TicketCollaborator,
    TicketRecord,
)
from coeus.services.audit import AuditLog
from coeus.services.embeddings import EmbeddingService
from coeus.services.similar_request_scoring import (
    CUSTOMER_SIMILARITY_THRESHOLD,
    MANAGER_SIMILARITY_THRESHOLD,
    OPEN_SIMILARITY_STATES,
    ROUTING_READ_PERMISSIONS,
    SimilarRequestMatch,
    score_similar_requests,
)
from coeus.services.ticket_records import is_collaborator, is_owner, timeline
from coeus.services.tickets import TicketServices

SIMILARITY_CANDIDATE_LIMIT = 100


class SimilarRequestService:
    """Coordinates customer notices and manager links for similar open tickets."""

    def __init__(
        self,
        tickets: TicketServices,
        audit_log: AuditLog,
        embeddings: EmbeddingService,
    ) -> None:
        self._tickets = tickets
        self._audit_log = audit_log
        self._embeddings = embeddings

    def customer_notice(
        self, actor: UserAccount, ticket_id: UUID
    ) -> tuple[SimilarRequestMatch, ...]:
        # Object-level check: the querying customer must be able to read the source ticket.
        source = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        # Only run for submitted, non-editable tickets. Draft or info-required tickets keep
        # their intake editable, which would let a customer replay the check as a probe. In
        # those states there is no notice to give, so return without scoring.
        if source.state not in OPEN_SIMILARITY_STATES:
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
            for match in self._score(source, candidates, CUSTOMER_SIMILARITY_THRESHOLD)
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

    def join_visible_match(
        self, actor: UserAccount, ticket_id: UUID, related_ticket_id: UUID
    ) -> TicketRecord:
        source = self._tickets.tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, source):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        target = self._tickets.tickets.get_visible_ticket(actor, related_ticket_id)
        match = self._find_match(source, target, CUSTOMER_SIMILARITY_THRESHOLD)
        if match is None:
            raise AppError(404, "similar_request_not_found", "Similar request was not found.")
        if is_owner(actor, target) or is_collaborator(actor, target):
            return target
        collaborator = TicketCollaborator(
            user_id=actor.user_id,
            username=actor.username,
            display_name=actor.display_name,
            access=CollaboratorAccess.VIEWER,
            added_by_user_id=actor.user_id,
            created_at=datetime.now(UTC),
        )
        proposed = replace(
            target,
            collaborators=(*target.collaborators, collaborator),
            timeline=(
                *target.timeline,
                timeline(
                    target.ticket_id,
                    actor.user_id,
                    "similar_request_joined",
                    f"{actor.display_name} joined from {source.reference}.",
                ),
            ),
        )
        return self._tickets.mutations.save_with_audits_if_current(
            target,
            proposed,
            actor,
            (
                (
                    "ticket_collaborator_added",
                    {
                        "ticket_id": str(target.ticket_id),
                        "collaborator_user_id": str(actor.user_id),
                        "access": CollaboratorAccess.VIEWER.value,
                    },
                ),
                (
                    "similar_request_joined",
                    {
                        "ticket_id": str(source.ticket_id),
                        "related_ticket_id": str(target.ticket_id),
                    },
                ),
            ),
        )

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
        return self._score(source, candidates, MANAGER_SIMILARITY_THRESHOLD)

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
        return self._find_match(source, related, MANAGER_SIMILARITY_THRESHOLD)

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

    def _score(
        self,
        source: TicketRecord,
        candidates: tuple[TicketRecord, ...],
        threshold: float,
    ) -> tuple[SimilarRequestMatch, ...]:
        return score_similar_requests(
            source,
            candidates,
            self._embeddings,
            threshold,
        )

    def _find_match(
        self, source: TicketRecord, related: TicketRecord, threshold: float
    ) -> SimilarRequestMatch | None:
        return next(iter(self._score(source, (related,), threshold)), None)

    @staticmethod
    def _bounded_candidates(
        source: TicketRecord, candidates: tuple[TicketRecord, ...]
    ) -> tuple[TicketRecord, ...]:
        eligible = (
            ticket
            for ticket in candidates
            if ticket.ticket_id != source.ticket_id and ticket.state in OPEN_SIMILARITY_STATES
        )
        return tuple(eligible)[:SIMILARITY_CANDIDATE_LIMIT]

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
