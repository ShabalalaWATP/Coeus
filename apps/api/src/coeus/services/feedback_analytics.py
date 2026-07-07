from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.qc import FeedbackRequest, FeedbackRequestStatus, FeedbackSubmission
from coeus.domain.tickets import ManagerRoutingDecisionStatus, RoutingRoute, TicketRecord
from coeus.services.audit import AuditLog
from coeus.services.store import StoreServices
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices
from coeus.services.trends_analysis import ProductReuseMetric, TrendInsight, TrendsAnalysisAgent


class AnalyticsAudience(StrEnum):
    ADMIN = "admin"
    RFA = "rfa"
    COLLECTION = "collection"


@dataclass(frozen=True)
class FeedbackSubmissionInput:
    rating: int
    comment: str
    follow_up_requested: bool


@dataclass(frozen=True)
class FeedbackRequestView:
    request: FeedbackRequest
    ticket: TicketRecord
    product_title: str
    submission: FeedbackSubmission | None


@dataclass(frozen=True)
class AnalyticsMetrics:
    total_tickets: int
    active_tickets: int
    disseminations: int
    feedback_requested: int
    feedback_submitted: int
    average_rating: float | None
    average_search_candidates: float | None
    rfa_routes: int
    collection_routes: int


@dataclass(frozen=True)
class AnalyticsDashboard:
    audience: AnalyticsAudience
    metrics: AnalyticsMetrics
    product_reuse: tuple[ProductReuseMetric, ...]
    trends: tuple[TrendInsight, ...]


class FeedbackAnalyticsService:
    def __init__(
        self,
        tickets: TicketServices,
        store: StoreServices,
        audit_log: AuditLog,
        trends_agent: TrendsAnalysisAgent | None = None,
    ) -> None:
        self._tickets = tickets
        self._store = store
        self._audit_log = audit_log
        self._trends = trends_agent or TrendsAnalysisAgent()

    def list_feedback_requests(self, actor: UserAccount) -> tuple[FeedbackRequestView, ...]:
        self._require(actor, Permission.FEEDBACK_CREATE)
        views = [
            self._feedback_view(actor, ticket, request)
            for ticket in self._tickets.tickets.list_visible_tickets(actor)
            for request in ticket.feedback_requests
            if request.requester_user_id == actor.user_id
        ]
        return tuple(sorted(views, key=lambda view: view.request.created_at, reverse=True))

    def submit_feedback(
        self,
        actor: UserAccount,
        request_id: UUID,
        payload: FeedbackSubmissionInput,
    ) -> FeedbackRequestView:
        self._require(actor, Permission.FEEDBACK_CREATE)
        ticket, request = self._find_request(actor, request_id)
        if request.status != FeedbackRequestStatus.REQUESTED:
            raise AppError(409, "feedback_already_submitted", "Feedback is already submitted.")
        comment = payload.comment.strip()
        if len(comment) < 3:
            raise AppError(422, "feedback_comment_required", "Feedback comment is required.")
        submission = FeedbackSubmission(
            submission_id=uuid4(),
            request_id=request.request_id,
            ticket_id=ticket.ticket_id,
            product_id=request.product_id,
            requester_user_id=actor.user_id,
            rating=payload.rating,
            comment=comment,
            follow_up_requested=payload.follow_up_requested,
            created_at=datetime.now(UTC),
        )
        updated_request = replace(request, status=FeedbackRequestStatus.SUBMITTED)
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                feedback_requests=tuple(
                    updated_request if item.request_id == request_id else item
                    for item in ticket.feedback_requests
                ),
                feedback_submissions=(*ticket.feedback_submissions, submission),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "feedback_submitted", comment),
                ),
            )
        )
        self._audit_log.record(
            "feedback_submitted",
            str(actor.user_id),
            {"ticket_id": str(ticket.ticket_id), "request_id": str(request_id)},
        )
        return self._feedback_view(actor, updated, updated_request)

    def dashboard(self, actor: UserAccount, audience: AnalyticsAudience) -> AnalyticsDashboard:
        tickets = self._tickets_for_audience(actor, audience)
        reuse = self._product_reuse(actor, tickets)
        metrics = self._metrics(tickets)
        return AnalyticsDashboard(
            audience=audience,
            metrics=metrics,
            product_reuse=reuse,
            trends=self._trends.analyse(tickets, reuse, metrics.average_rating),
        )

    def _tickets_for_audience(
        self, actor: UserAccount, audience: AnalyticsAudience
    ) -> tuple[TicketRecord, ...]:
        if audience == AnalyticsAudience.ADMIN:
            self._require(actor, Permission.ANALYTICS_VIEW_GLOBAL)
            return self._tickets.tickets.list_visible_tickets(actor)
        self._require(actor, Permission.ANALYTICS_VIEW_TEAM)
        route = RoutingRoute.RFA if audience == AnalyticsAudience.RFA else RoutingRoute.CM
        review_permission = (
            Permission.RFA_REVIEW if route == RoutingRoute.RFA else Permission.COLLECTION_REVIEW
        )
        self._require(actor, review_permission)
        tickets = self._tickets.tickets.list_workflow_tickets(actor, frozenset({review_permission}))
        return tuple(ticket for ticket in tickets if _route_scoped(ticket, route))

    def _find_request(
        self, actor: UserAccount, request_id: UUID
    ) -> tuple[TicketRecord, FeedbackRequest]:
        for ticket in self._tickets.tickets.list_visible_tickets(actor):
            for request in ticket.feedback_requests:
                if request.request_id == request_id and request.requester_user_id == actor.user_id:
                    return ticket, request
        raise AppError(404, "feedback_request_not_found", "Feedback request was not found.")

    def _feedback_view(
        self, actor: UserAccount, ticket: TicketRecord, request: FeedbackRequest
    ) -> FeedbackRequestView:
        return FeedbackRequestView(
            request=request,
            ticket=ticket,
            product_title=_product_title(self._store, actor, request.product_id),
            submission=_submission_for(ticket, request.request_id),
        )

    def _metrics(self, tickets: tuple[TicketRecord, ...]) -> AnalyticsMetrics:
        submissions = [item for ticket in tickets for item in ticket.feedback_submissions]
        search_metrics = [item for ticket in tickets for item in ticket.search_metrics]
        return AnalyticsMetrics(
            total_tickets=len(tickets),
            active_tickets=sum(1 for ticket in tickets if _is_active(ticket)),
            disseminations=sum(len(ticket.disseminations) for ticket in tickets),
            feedback_requested=sum(len(ticket.feedback_requests) for ticket in tickets),
            feedback_submitted=len(submissions),
            average_rating=_average([item.rating for item in submissions]),
            average_search_candidates=_average([item.candidate_count for item in search_metrics]),
            rfa_routes=sum(1 for ticket in tickets if _approved_route(ticket) == RoutingRoute.RFA),
            collection_routes=sum(
                1 for ticket in tickets if _approved_route(ticket) == RoutingRoute.CM
            ),
        )

    def _product_reuse(
        self, actor: UserAccount, tickets: tuple[TicketRecord, ...]
    ) -> tuple[ProductReuseMetric, ...]:
        dissemination_product_ids = {
            item.product_id for ticket in tickets for item in ticket.disseminations
        }
        feedback_product_ids = {
            item.product_id for ticket in tickets for item in ticket.feedback_submissions
        }
        accepted_product_ids = {
            offer.product_id
            for ticket in tickets
            for offer in ticket.product_offers
            if offer.status.value == "accepted"
        }
        product_ids = dissemination_product_ids | feedback_product_ids | accepted_product_ids
        metrics = tuple(
            metric
            for product_id in product_ids
            if (metric := self._reuse_metric(actor, product_id, tickets)) is not None
        )
        return tuple(
            sorted(
                metrics,
                key=lambda item: (
                    -(item.dissemination_count + item.accepted_offer_count),
                    item.title,
                ),
            )
        )

    def _reuse_metric(
        self, actor: UserAccount, product_id: UUID, tickets: tuple[TicketRecord, ...]
    ) -> ProductReuseMetric | None:
        try:
            product = self._store.details.get_visible_product(actor, product_id)
        except AppError:
            return None
        submissions = [
            item
            for ticket in tickets
            for item in ticket.feedback_submissions
            if item.product_id == product_id
        ]
        return ProductReuseMetric(
            product_id=product_id,
            reference=product.reference,
            title=product.metadata.title,
            owner_team=product.metadata.owner_team,
            dissemination_count=sum(
                1
                for ticket in tickets
                for item in ticket.disseminations
                if item.product_id == product_id
            ),
            accepted_offer_count=sum(
                1
                for ticket in tickets
                for item in ticket.product_offers
                if item.product_id == product_id and item.status.value == "accepted"
            ),
            feedback_count=len(submissions),
            average_rating=_average([item.rating for item in submissions]),
        )

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")


def build_feedback_analytics_service(
    tickets: TicketServices, store: StoreServices, audit_log: AuditLog
) -> FeedbackAnalyticsService:
    return FeedbackAnalyticsService(tickets, store, audit_log)


def _is_active(ticket: TicketRecord) -> bool:
    """Closed and cancelled tickets are not active work in progress."""
    return not ticket.state.name.startswith("CLOSED") and ticket.state != TicketState.CANCELLED


def _approved_route(ticket: TicketRecord) -> RoutingRoute | None:
    for decision in reversed(ticket.manager_decisions):
        if decision.status == ManagerRoutingDecisionStatus.APPROVED:
            return decision.route
    return None


def _route_scoped(ticket: TicketRecord, route: RoutingRoute) -> bool:
    if _approved_route(ticket) == route:
        return True
    if ticket.manager_decisions and ticket.manager_decisions[-1].route == route:
        return True
    return (
        bool(ticket.route_recommendations)
        and ticket.route_recommendations[-1].recommended_route == route
    )


def _submission_for(ticket: TicketRecord, request_id: UUID) -> FeedbackSubmission | None:
    for submission in ticket.feedback_submissions:
        if submission.request_id == request_id:
            return submission
    return None


def _product_title(store: StoreServices, actor: UserAccount, product_id: UUID) -> str:
    try:
        return store.details.get_visible_product(actor, product_id).metadata.title
    except AppError:
        return "Unknown product"


def _average(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)
