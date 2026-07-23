from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.agent_names import SEARCH_PLANNER_AGENT
from coeus.domain.auth import AuthenticatedSession, SessionRecord, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.search_index import GroundedProductEvidence
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.store import StoreSearchFilters
from coeus.domain.tickets import (
    ProductDissemination,
    ProductOfferStatus,
    TicketRecord,
)
from coeus.domain.workflow_authority import RfiCommitAuthority, WorkflowCommitAuthority
from coeus.services.advisory_records import advisory_agent_run
from coeus.services.embeddings import EmbeddingService
from coeus.services.grounded_search import GroundedSearchService
from coeus.services.rfi_records import (
    accepted_metric,
    active_offer,
    complete_agent_run,
    rejected_metric,
    run_summary,
    set_offer_status,
    timeline,
)
from coeus.services.rfi_result_projection import project_rfi_result_signal
from coeus.services.rfi_search_assurance import (
    RFI_RESULTS_REVIEW_PERMISSIONS,
    RFI_RESULTS_REVIEW_STATES,
    decide_search_outcome,
    state_after_all_offers_rejected,
)
from coeus.services.rfi_search_retrieval import (
    RFI_CANDIDATE_SEARCH_LIMIT,
    ranked_additive_offers,
    retrieve_with_additive_advice,
)
from coeus.services.rfi_search_types import RfiAccess, RfiSearchResults
from coeus.services.search_planner_agent import SearchPlannerAgent
from coeus.services.store import StoreSearchService
from coeus.services.store_access import StoreDetailService
from coeus.services.ticket_mutations import TicketMutationService
from coeus.services.ticket_records import is_editor, is_owner
from coeus.services.tickets import TicketService


class RfiSearchService:
    def __init__(
        self,
        tickets: TicketService,
        store_search: StoreSearchService,
        store_details: StoreDetailService,
        access_repository: RfiAccess,
        embeddings: EmbeddingService,
        grounded: GroundedSearchService,
        planner: SearchPlannerAgent,
        mutations: TicketMutationService,
    ) -> None:
        self._tickets = tickets
        self._store_search = store_search
        self._store_details = store_details
        self._access_repository = access_repository
        self._embeddings = embeddings
        self._grounded = grounded
        self._planner = planner
        self._mutations = mutations

    def run(self, authenticated: AuthenticatedSession, ticket_id: UUID) -> RfiSearchResults:
        return self._run(authenticated.user, authenticated.session, ticket_id)

    def run_automated(self, actor: UserAccount, ticket_id: UUID) -> RfiSearchResults:
        """Run trusted outbox retrieval without an end-user session requirement."""
        return self._run(actor, None, ticket_id)

    def _run(
        self,
        actor: UserAccount,
        session: SessionRecord | None,
        ticket_id: UUID,
    ) -> RfiSearchResults:
        self._require(actor, Permission.RFI_SEARCH)
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not self._can_run_search(actor, ticket):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        if ticket.state not in {TicketState.RFI_SEARCHING, TicketState.RFI_SEARCH_INCOMPLETE}:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting RFI search.")
        requester = self._requester(ticket)
        requester_acgs = self._access_repository.active_acg_ids_for_user(requester.user_id)
        search = self._store_search.search(
            requester,
            StoreSearchFilters(
                status=ProductStatus.PUBLISHED,
                page_size=RFI_CANDIDATE_SEARCH_LIMIT,
            ),
        )
        retrieval = retrieve_with_additive_advice(
            requester,
            ticket,
            actor.user_id,
            self._planner,
            self._embeddings,
            self._store_search,
            self._store_details,
            self._grounded,
        )
        plan = retrieval.plan
        grounded = retrieval.grounded
        offers = ranked_additive_offers(retrieval, ticket)
        decision = decide_search_outcome(len(offers), grounded)
        now = datetime.now(UTC)
        summary = run_summary(len(offers), search.total)
        planner_run = advisory_agent_run(
            ticket.ticket_id,
            SEARCH_PLANNER_AGENT,
            "Advised bounded terminology for authorised product retrieval.",
            plan.record,
            created_at=now,
        )
        agent_runs, run_id = complete_agent_run(ticket, summary, now)
        search_index = next(index for index, run in enumerate(agent_runs) if run.run_id == run_id)
        agent_runs = (
            *agent_runs[:search_index],
            planner_run,
            *agent_runs[search_index:],
        )
        search_timeline = [
            timeline(ticket.ticket_id, actor.user_id, "search_completed", summary),
        ]
        if decision.outcome == "no_match":
            search_timeline.append(
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "rfi_no_match",
                    "No existing product matched this request.",
                )
            )
        elif decision.outcome == "incomplete":
            search_timeline.append(
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "rfi_search_degraded",
                    "Search coverage was incomplete; no definitive no-match was recorded.",
                )
            )
        metric = RfiSearchMetrics(
            run_id=run_id,
            query=retrieval.base_query,
            candidate_count=search.total,
            offered_count=len(offers),
            rejected_count=0,
            accepted_product_id=None,
            created_at=now,
            retrieval_mode=grounded.retrieval_mode,
            degraded_reason=grounded.degraded_reason,
            outcome=decision.outcome,
            assurance=decision.assurance,
            coverage_status=grounded.coverage_status,
            profile_space_id=grounded.profile_space_id,
            corpus_version=grounded.corpus_version,
        )
        updated = self._mutations.save_authorised_audited_if_current(
            ticket,
            replace(
                ticket,
                state=decision.state,
                agent_runs=agent_runs,
                product_offers=offers,
                search_evidence=grounded.evidence,
                search_metrics=(*ticket.search_metrics, metric),
                visible_product_matches=tuple(offer.title for offer in offers),
                timeline=(*ticket.timeline, *search_timeline),
            ),
            "rfi_search_completed",
            WorkflowCommitAuthority(
                actor,
                session,
                frozenset({Permission.RFI_SEARCH}),
                rfi=RfiCommitAuthority(
                    requester,
                    requester_acgs,
                    frozenset(offer.product_id for offer in offers).union(
                        evidence.product_id for evidence in grounded.evidence
                    ),
                ),
            ),
            {"ticket_id": str(ticket.ticket_id), "offered_count": str(len(offers))},
        )
        return self._results_for(actor, updated, grounded.evidence)

    def results(self, actor: UserAccount, ticket_id: UUID) -> RfiSearchResults:
        return self._results_for(actor, self._results_ticket(actor, ticket_id))

    def visible_offer_product_ids(
        self, actor: UserAccount, tickets: tuple[TicketRecord, ...]
    ) -> frozenset[UUID]:
        candidate_ids = frozenset(
            offer.product_id for ticket in tickets for offer in ticket.product_offers
        )
        return self._store_details.visible_product_ids(actor, candidate_ids)

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
        updated = self._mutations.save_audited_if_current(
            ticket,
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
            ),
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
        metric = rejected_metric(ticket, offers)
        next_state = TicketState.RFI_MATCH_OFFERED
        if not any(item.status == ProductOfferStatus.OFFERED for item in offers):
            next_state = state_after_all_offers_rejected(metric)
        updated = self._mutations.save_audited_if_current(
            ticket,
            replace(
                ticket,
                state=next_state,
                product_offers=offers,
                search_metrics=(*ticket.search_metrics[:-1], metric),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "product_offer_rejected", reason),
                ),
            ),
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

    def _results_for(
        self,
        actor: UserAccount,
        ticket: TicketRecord,
        evidence: tuple[GroundedProductEvidence, ...] | None = None,
    ) -> RfiSearchResults:
        visible_ids = self.visible_offer_product_ids(actor, (ticket,))
        ticket = project_rfi_result_signal(
            ticket,
            visible_ids,
            preserve_full=ticket.requester_user_id == actor.user_id,
        )
        visible_offers = ticket.product_offers
        metric = ticket.search_metrics[-1] if ticket.search_metrics else None
        if evidence is None:
            evidence = ticket.search_evidence
        visible_evidence = tuple(
            item for item in (evidence or ()) if item.product_id in visible_ids
        )
        return RfiSearchResults(
            ticket=ticket,
            offers=visible_offers,
            metrics=metric,
            evidence=visible_evidence,
            retrieval_mode=metric.retrieval_mode if metric else "metadata_only",
            degraded_reason=metric.degraded_reason if metric else None,
            outcome=metric.outcome if metric else "incomplete",
            assurance=metric.assurance if metric else "assisted",
        )

    def _requester(self, ticket: TicketRecord) -> UserAccount:
        requester = self._access_repository.get_user(ticket.requester_user_id)
        if requester is None or not requester.is_active:
            raise AppError(409, "requester_unavailable", "Ticket requester is unavailable.")
        return requester

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
