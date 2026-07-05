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
    AgentRun,
    AgentRunStatus,
    ProductDissemination,
    ProductOffer,
    ProductOfferStatus,
    RfiSearchMetrics,
    TicketRecord,
    TicketTimelineEntry,
)
from coeus.repositories.access import SeedAccessRepository
from coeus.services.audit import AuditLog
from coeus.services.rfi_ranking import query_text, rank_rfi_hits
from coeus.services.store import StoreDetailService, StoreSearchService, StoreServices
from coeus.services.tickets import TicketService, TicketServices

RFI_RESULTS_REVIEW_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})
RFI_RESULTS_REVIEW_STATES = frozenset(
    {TicketState.ROUTE_ASSESSMENT, TicketState.RFA_MANAGER_REVIEW, TicketState.CM_MANAGER_REVIEW}
)


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
        access_repository: SeedAccessRepository,
        audit_log: AuditLog,
    ) -> None:
        self._tickets = tickets
        self._store_search = store_search
        self._store_details = store_details
        self._access_repository = access_repository
        self._audit_log = audit_log

    def run(self, actor: UserAccount, ticket_id: UUID) -> RfiSearchResults:
        self._require(actor, Permission.RFI_SEARCH)
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if ticket.state != TicketState.RFI_SEARCHING:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting RFI search.")
        requester = self._requester(ticket)
        search = self._store_search.search(
            requester,
            StoreSearchFilters(status=ProductStatus.PUBLISHED),
        )
        query = query_text(ticket.intake)
        offers = rank_rfi_hits(search.hits, ticket.intake)
        target_state = TicketState.RFI_MATCH_OFFERED if offers else TicketState.ROUTE_ASSESSMENT
        now = datetime.now(UTC)
        summary = _run_summary(len(offers), search.total)
        agent_runs, run_id = _complete_agent_run(ticket, summary, now)
        metric = RfiSearchMetrics(
            run_id=run_id,
            query=query,
            candidate_count=search.total,
            offered_count=len(offers),
            rejected_count=0,
            accepted_product_id=None,
            created_at=now,
        )
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                state=target_state,
                agent_runs=agent_runs,
                product_offers=offers,
                search_metrics=(*ticket.search_metrics, metric),
                visible_product_matches=tuple(offer.title for offer in offers),
                timeline=(
                    *ticket.timeline,
                    _timeline(ticket.ticket_id, actor.user_id, "search_completed", summary),
                ),
            )
        )
        self._audit_log.record(
            "rfi_search_completed",
            str(actor.user_id),
            {"ticket_id": str(ticket.ticket_id), "offered_count": str(len(offers))},
        )
        return self._results_for(actor, updated)

    def results(self, actor: UserAccount, ticket_id: UUID) -> RfiSearchResults:
        return self._results_for(actor, self._results_ticket(actor, ticket_id))

    def accept(self, actor: UserAccount, ticket_id: UUID, product_id: UUID) -> RfiSearchResults:
        self._require(actor, Permission.RFI_ACCEPT_PRODUCT)
        ticket = self._offer_ticket(actor, ticket_id)
        offer = _active_offer(ticket, product_id)
        self._store_details.get_visible_product(actor, offer.product_id)
        now = datetime.now(UTC)
        offers = _set_offer_status(ticket.product_offers, product_id, ProductOfferStatus.ACCEPTED)
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
                search_metrics=(*ticket.search_metrics[:-1], _accepted_metric(ticket, product_id)),
                timeline=(
                    *ticket.timeline,
                    _timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "product_offer_accepted",
                        f"Accepted existing product {offer.title}.",
                    ),
                ),
            )
        )
        self._audit_log.record(
            "product_offer_accepted",
            str(actor.user_id),
            {"ticket_id": str(ticket.ticket_id), "product_id": str(product_id)},
        )
        return self._results_for(actor, updated)

    def reject(
        self, actor: UserAccount, ticket_id: UUID, product_id: UUID, reason: str
    ) -> RfiSearchResults:
        self._require(actor, Permission.RFI_REJECT_PRODUCT)
        ticket = self._offer_ticket(actor, ticket_id)
        offer = _active_offer(ticket, product_id)
        self._store_details.get_visible_product(actor, offer.product_id)
        offers = _set_offer_status(
            ticket.product_offers,
            product_id,
            ProductOfferStatus.REJECTED,
            reason.strip(),
        )
        next_state = (
            TicketState.ROUTE_ASSESSMENT
            if not any(item.status == ProductOfferStatus.OFFERED for item in offers)
            else TicketState.RFI_MATCH_OFFERED
        )
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                state=next_state,
                product_offers=offers,
                search_metrics=(*ticket.search_metrics[:-1], _rejected_metric(ticket, offers)),
                timeline=(
                    *ticket.timeline,
                    _timeline(ticket.ticket_id, actor.user_id, "product_offer_rejected", reason),
                ),
            )
        )
        self._audit_log.record(
            "product_offer_rejected",
            str(actor.user_id),
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
            metric = replace(
                metric,
                candidate_count=len(visible_offers),
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

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")


def _active_offer(ticket: TicketRecord, product_id: UUID) -> ProductOffer:
    for offer in ticket.product_offers:
        if offer.product_id == product_id and offer.status == ProductOfferStatus.OFFERED:
            return offer
    raise AppError(404, "product_offer_not_found", "Product offer was not found.")


def _set_offer_status(
    offers: tuple[ProductOffer, ...],
    product_id: UUID,
    status: ProductOfferStatus,
    rejection_reason: str | None = None,
) -> tuple[ProductOffer, ...]:
    return tuple(
        replace(offer, status=status, rejection_reason=rejection_reason)
        if offer.product_id == product_id
        else offer
        for offer in offers
    )


def _complete_agent_run(
    ticket: TicketRecord, summary: str, now: datetime
) -> tuple[tuple[AgentRun, ...], UUID]:
    for run in ticket.agent_runs:
        if run.agent_name == "rfi-search" and run.status == AgentRunStatus.QUEUED:
            updated = replace(
                run,
                status=AgentRunStatus.COMPLETED,
                summary=summary,
                created_at=now,
            )
            runs = tuple(
                updated if item.run_id == run.run_id else item for item in ticket.agent_runs
            )
            return runs, run.run_id
    run = AgentRun(
        uuid4(),
        ticket.ticket_id,
        "rfi-search",
        AgentRunStatus.COMPLETED,
        summary,
        (),
        now,
    )
    return (*ticket.agent_runs, run), run.run_id


def _accepted_metric(ticket: TicketRecord, product_id: UUID) -> RfiSearchMetrics:
    metric = ticket.search_metrics[-1]
    return replace(metric, accepted_product_id=product_id)


def _rejected_metric(ticket: TicketRecord, offers: tuple[ProductOffer, ...]) -> RfiSearchMetrics:
    metric = ticket.search_metrics[-1]
    return replace(
        metric,
        rejected_count=sum(offer.status == ProductOfferStatus.REJECTED for offer in offers),
    )


def _timeline(
    ticket_id: UUID, actor_user_id: UUID, event_type: str, body: str
) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        uuid4(),
        ticket_id,
        event_type,
        body,
        actor_user_id,
        datetime.now(UTC),
    )


def _run_summary(offer_count: int, candidate_count: int) -> str:
    if offer_count:
        return (
            f"Search completed with {offer_count} offer(s) from "
            f"{candidate_count} permitted candidate(s)."
        )
    return (
        "No permitted existing product exceeded the offer threshold from "
        f"{candidate_count} candidate(s)."
    )


def build_rfi_search_service(
    ticket_services: TicketServices,
    store_services: StoreServices,
    access_repository: SeedAccessRepository,
    audit_log: AuditLog,
) -> RfiSearchService:
    return RfiSearchService(
        ticket_services.tickets,
        store_services.search,
        store_services.details,
        access_repository,
        audit_log,
    )
