from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.store import StoreSearchFilters
from coeus.domain.tickets import (
    ProductDissemination,
    ProductOffer,
    ProductOfferStatus,
    RfiSearchMetrics,
    TicketRecord,
)
from coeus.repositories.access import AccessRepository
from coeus.services.audit import AuditLog
from coeus.services.embeddings import EmbeddingService
from coeus.services.rfi_ranking import query_text, rank_hybrid_rfi_candidates
from coeus.services.rfi_records import (
    accepted_metric,
    active_offer,
    complete_agent_run,
    rejected_metric,
    run_summary,
    set_offer_status,
    timeline,
)
from coeus.services.store import StoreSearchService, StoreServices
from coeus.services.store_access import StoreDetailService
from coeus.services.ticket_records import is_editor, is_owner
from coeus.services.tickets import TicketService, TicketServices

RFI_RESULTS_REVIEW_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})
RFI_RESULTS_REVIEW_STATES = frozenset(
    {
        TicketState.RFI_NO_MATCH,
        TicketState.JIOC_REVIEW,
        TicketState.COLLECT_CHOICE,
    }
)
# Ranking must see every permitted PUBLISHED product, not the store-browse page
# size, so the candidate search uses one large internal page.
RFI_CANDIDATE_SEARCH_LIMIT = 500


@dataclass(frozen=True)
class RfiSearchResults:
    ticket: TicketRecord
    offers: tuple[ProductOffer, ...]
    metrics: RfiSearchMetrics | None


class RfiSearchService:
    def __init__(
        self,
        tickets: TicketService,
        store_search: StoreSearchService,
        store_details: StoreDetailService,
        access_repository: AccessRepository,
        audit_log: AuditLog,
        embeddings: EmbeddingService,
    ) -> None:
        self._tickets = tickets
        self._store_search = store_search
        self._store_details = store_details
        self._access_repository = access_repository
        self._audit_log = audit_log
        self._embeddings = embeddings

    def run(self, actor: UserAccount, ticket_id: UUID) -> RfiSearchResults:
        self._require(actor, Permission.RFI_SEARCH)
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not self._can_run_search(actor, ticket):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        if ticket.state != TicketState.RFI_SEARCHING:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting RFI search.")
        requester = self._requester(ticket)
        search = self._store_search.search(
            requester,
            StoreSearchFilters(
                status=ProductStatus.PUBLISHED,
                page_size=RFI_CANDIDATE_SEARCH_LIMIT,
            ),
        )
        query = query_text(ticket.intake)
        query_embedding = self._embeddings.embed(query, purpose="rfi-query")
        candidates = self._store_search.hybrid_candidates(
            requester,
            StoreSearchFilters(
                status=ProductStatus.PUBLISHED,
                page_size=RFI_CANDIDATE_SEARCH_LIMIT,
            ),
            query,
            query_embedding,
        )
        offers = rank_hybrid_rfi_candidates(candidates, ticket.intake)
        target_state = TicketState.RFI_MATCH_OFFERED if offers else TicketState.RFI_NO_MATCH
        now = datetime.now(UTC)
        summary = run_summary(len(offers), search.total)
        agent_runs, run_id = complete_agent_run(ticket, summary, now)
        search_timeline = [
            timeline(ticket.ticket_id, actor.user_id, "search_completed", summary),
        ]
        if not offers:
            search_timeline.append(
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "rfi_no_match",
                    "No existing product matched this request.",
                )
            )
        metric = RfiSearchMetrics(
            run_id=run_id,
            query=query,
            candidate_count=search.total,
            offered_count=len(offers),
            rejected_count=0,
            accepted_product_id=None,
            created_at=now,
        )
        updated = self._tickets.save_system_update_if_current(
            ticket,
            replace(
                ticket,
                state=target_state,
                agent_runs=agent_runs,
                product_offers=offers,
                search_metrics=(*ticket.search_metrics, metric),
                visible_product_matches=tuple(offer.title for offer in offers),
                timeline=(*ticket.timeline, *search_timeline),
            ),
        )
        self._record_audit_or_rollback(
            ticket,
            updated,
            "rfi_search_completed",
            actor,
            {"ticket_id": str(ticket.ticket_id), "offered_count": str(len(offers))},
        )
        return self._results_for(actor, updated)

    def results(self, actor: UserAccount, ticket_id: UUID) -> RfiSearchResults:
        return self._results_for(actor, self._results_ticket(actor, ticket_id))

    def accept(self, actor: UserAccount, ticket_id: UUID, product_id: UUID) -> RfiSearchResults:
        self._require(actor, Permission.RFI_ACCEPT_PRODUCT)
        ticket = self._offer_ticket(actor, ticket_id)
        offer = active_offer(ticket, product_id)
        self._store_details.get_visible_product(actor, offer.product_id)
        now = datetime.now(UTC)
        offers = set_offer_status(ticket.product_offers, product_id, ProductOfferStatus.ACCEPTED)
        dissemination = ProductDissemination(
            dissemination_id=uuid4(),
            ticket_id=ticket.ticket_id,
            product_id=product_id,
            recipient_user_id=actor.user_id,
            created_at=now,
        )
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
                product_offers=offers,
                disseminations=(*ticket.disseminations, dissemination),
                search_metrics=(*ticket.search_metrics[:-1], accepted_metric(ticket, product_id)),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "product_offer_accepted",
                        f"Accepted existing product {offer.title}.",
                    ),
                ),
            )
        )
        self._record_audit_or_rollback(
            ticket,
            updated,
            "product_offer_accepted",
            actor,
            {"ticket_id": str(ticket.ticket_id), "product_id": str(product_id)},
        )
        return self._results_for(actor, updated)

    def reject(
        self, actor: UserAccount, ticket_id: UUID, product_id: UUID, reason: str
    ) -> RfiSearchResults:
        self._require(actor, Permission.RFI_REJECT_PRODUCT)
        ticket = self._offer_ticket(actor, ticket_id)
        offer = active_offer(ticket, product_id)
        self._store_details.get_visible_product(actor, offer.product_id)
        offers = set_offer_status(
            ticket.product_offers,
            product_id,
            ProductOfferStatus.REJECTED,
            reason.strip(),
        )
        next_state = (
            TicketState.JIOC_REVIEW
            if not any(item.status == ProductOfferStatus.OFFERED for item in offers)
            else TicketState.RFI_MATCH_OFFERED
        )
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                state=next_state,
                product_offers=offers,
                search_metrics=(*ticket.search_metrics[:-1], rejected_metric(ticket, offers)),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "product_offer_rejected", reason),
                ),
            )
        )
        self._record_audit_or_rollback(
            ticket,
            updated,
            "product_offer_rejected",
            actor,
            {"ticket_id": str(ticket.ticket_id), "product_id": str(product_id)},
        )
        return self._results_for(actor, updated)

    def _offer_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if ticket.requester_user_id != actor.user_id:
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        if ticket.state != TicketState.RFI_MATCH_OFFERED:
            raise AppError(409, "invalid_ticket_state", "Ticket has no active product offers.")
        return ticket

    @staticmethod
    def _can_run_search(actor: UserAccount, ticket: TicketRecord) -> bool:
        return (
            is_owner(actor, ticket)
            or is_editor(actor, ticket)
            or Permission.TICKET_WRITE_ALL in actor.permissions
        )

    def _results_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        try:
            return self._tickets.get_visible_ticket(actor, ticket_id)
        except AppError:
            ticket = self._tickets.get_workflow_ticket(
                actor, ticket_id, RFI_RESULTS_REVIEW_PERMISSIONS
            )
            if ticket.state not in RFI_RESULTS_REVIEW_STATES:
                raise AppError(404, "ticket_not_found", "Ticket was not found.") from None
            return ticket

    def _results_for(self, actor: UserAccount, ticket: TicketRecord) -> RfiSearchResults:
        visible_offers = tuple(
            offer for offer in ticket.product_offers if self._can_read_offer(actor, offer)
        )
        metric = ticket.search_metrics[-1] if ticket.search_metrics else None
        if metric is not None and len(visible_offers) != len(ticket.product_offers):
            # candidate_count stays the permitted candidate total from the search
            # run; only the offer counts are re-scoped to what this viewer can see.
            metric = replace(
                metric,
                offered_count=len(visible_offers),
                rejected_count=sum(
                    offer.status == ProductOfferStatus.REJECTED for offer in visible_offers
                ),
            )
        return RfiSearchResults(ticket=ticket, offers=visible_offers, metrics=metric)

    def _requester(self, ticket: TicketRecord) -> UserAccount:
        requester = self._access_repository.get_user(ticket.requester_user_id)
        if requester is None or not requester.is_active:
            raise AppError(409, "requester_unavailable", "Ticket requester is unavailable.")
        return requester

    def _can_read_offer(self, actor: UserAccount, offer: ProductOffer) -> bool:
        try:
            self._store_details.get_visible_product(actor, offer.product_id)
        except AppError:
            return False
        return True

    def _record_audit_or_rollback(
        self,
        original_ticket: TicketRecord,
        updated_ticket: TicketRecord,
        event_type: str,
        actor: UserAccount,
        details: dict[str, str],
    ) -> None:
        try:
            self._audit_log.record(event_type, str(actor.user_id), details)
        except Exception:
            self._tickets.restore_system_update_if_current(updated_ticket, original_ticket)
            raise

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")


def build_rfi_search_service(
    ticket_services: TicketServices,
    store_services: StoreServices,
    access_repository: AccessRepository,
    audit_log: AuditLog,
    embeddings: EmbeddingService,
) -> RfiSearchService:
    return RfiSearchService(
        ticket_services.tickets,
        store_services.search,
        store_services.details,
        access_repository,
        audit_log,
        embeddings,
    )
