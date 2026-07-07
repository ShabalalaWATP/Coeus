from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import (
    AgentRun,
    AgentRunStatus,
    CmCapabilityReview,
    ManagerRoutingDecision,
    ManagerRoutingDecisionStatus,
    ProjectPlanUpdate,
    RfaCapabilityReview,
    RouteRecommendation,
    RoutingRoute,
    TicketRecord,
    TicketTimelineEntry,
)


def latest_recommendation(ticket: TicketRecord) -> RouteRecommendation:
    if not ticket.route_recommendations:
        raise AppError(409, "missing_route_recommendation", "Run capability reviews first.")
    return ticket.route_recommendations[-1]


def latest_cm_review(ticket: TicketRecord) -> CmCapabilityReview | None:
    return ticket.cm_reviews[-1] if ticket.cm_reviews else None


def recommend_route(
    ticket_id: UUID,
    rfa_review: RfaCapabilityReview,
    cm_review: CmCapabilityReview,
) -> RouteRecommendation:
    if rfa_review.can_satisfy and rfa_review.confidence >= 0.65:
        route = RoutingRoute.RFA
        reason = "RFA route preferred because assessment can satisfy the request."
    elif cm_review.can_satisfy:
        route = RoutingRoute.CM
        reason = "CM route selected because RFA cannot satisfy and collection can."
    else:
        route = RoutingRoute.CLARIFICATION
        reason = "Clarification is required before RFA or CM approval."
    return RouteRecommendation(
        uuid4(),
        ticket_id,
        route,
        reason,
        rfa_review.review_id,
        cm_review.review_id,
        datetime.now(UTC),
    )


def state_for_recommendation(recommendation: RouteRecommendation) -> TicketState:
    return {
        RoutingRoute.RFA: TicketState.RFA_MANAGER_REVIEW,
        RoutingRoute.CM: TicketState.CM_MANAGER_REVIEW,
        RoutingRoute.CLARIFICATION: TicketState.INFO_REQUIRED,
    }[recommendation.recommended_route]


def fallback_state(route: RoutingRoute, cm_review: CmCapabilityReview | None) -> TicketState:
    if route == RoutingRoute.RFA and cm_review is not None and cm_review.can_satisfy:
        return TicketState.CM_MANAGER_REVIEW
    return TicketState.INFO_REQUIRED


def can_review_route(actor: UserAccount, ticket: TicketRecord) -> bool:
    if Permission.TICKET_READ_ALL in actor.permissions:
        return True
    reviewer = (
        Permission.RFA_REVIEW in actor.permissions
        or Permission.COLLECTION_REVIEW in actor.permissions
    )
    return (
        (
            ticket.state == TicketState.RFA_MANAGER_REVIEW
            and Permission.RFA_REVIEW in actor.permissions
        )
        or (
            ticket.state == TicketState.CM_MANAGER_REVIEW
            and Permission.COLLECTION_REVIEW in actor.permissions
        )
        or (
            ticket.state in {TicketState.ROUTE_ASSESSMENT, TicketState.MANAGER_RELEASE} and reviewer
        )
    )


def filled(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def decision(
    ticket_id: UUID,
    actor_user_id: UUID,
    route: RoutingRoute,
    status: ManagerRoutingDecisionStatus,
    reason: str,
    override_reason: str | None,
) -> ManagerRoutingDecision:
    return ManagerRoutingDecision(
        decision_id=uuid4(),
        ticket_id=ticket_id,
        route=route,
        status=status,
        reason=reason,
        override_reason=override_reason.strip() if override_reason else None,
        actor_user_id=actor_user_id,
        created_at=datetime.now(UTC),
    )


def agent_run(ticket_id: UUID, agent_name: str, summary: str) -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        ticket_id=ticket_id,
        agent_name=agent_name,
        status=AgentRunStatus.COMPLETED,
        summary=summary,
        safety_flags=(),
        created_at=datetime.now(UTC),
    )


def review_agent_runs(
    ticket_id: UUID,
    rfa_review: RfaCapabilityReview,
    cm_review: CmCapabilityReview,
    recommendation: RouteRecommendation,
) -> tuple[AgentRun, ...]:
    return (
        agent_run(ticket_id, "rfa-capability-agent", rfa_review.reasoning_summary),
        agent_run(ticket_id, "cm-capability-agent", cm_review.reasoning_summary),
        agent_run(ticket_id, "orchestrator-agent", recommendation.reasoning_summary),
    )


def project_update(
    ticket_id: UUID,
    state: TicketState,
    recommendation: RouteRecommendation,
) -> ProjectPlanUpdate:
    return ProjectPlanUpdate(
        update_id=uuid4(),
        ticket_id=ticket_id,
        title=_plan_title_for_state(state),
        owner_role=_owner_for_route(recommendation.recommended_route),
        status="proposed",
        note=recommendation.reasoning_summary,
        created_at=datetime.now(UTC),
    )


def decision_project_update(
    ticket_id: UUID,
    manager_decision: ManagerRoutingDecision,
    state: TicketState,
) -> ProjectPlanUpdate:
    return ProjectPlanUpdate(
        update_id=uuid4(),
        ticket_id=ticket_id,
        title=_plan_title_for_state(state),
        owner_role=_owner_for_route(manager_decision.route),
        status=manager_decision.status.value,
        note=manager_decision.override_reason or manager_decision.reason,
        created_at=datetime.now(UTC),
    )


def timeline(
    ticket_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    body: str,
) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        entry_id=uuid4(),
        ticket_id=ticket_id,
        event_type=event_type,
        body=body,
        actor_user_id=actor_user_id,
        created_at=datetime.now(UTC),
    )


def count_state(tickets: tuple[TicketRecord, ...], state: TicketState) -> int:
    return sum(1 for ticket in tickets if ticket.state == state)


def rate(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part / total, 2)


def _plan_title_for_state(state: TicketState) -> str:
    if state == TicketState.ANALYST_ASSIGNMENT:
        return "Prepare analyst assignment"
    if state == TicketState.CM_MANAGER_REVIEW:
        return "Collection manager route review"
    if state == TicketState.RFA_MANAGER_REVIEW:
        return "RFA manager route review"
    return "Clarify routing requirement"


def _owner_for_route(route: RoutingRoute) -> str:
    return {
        RoutingRoute.RFA: "RFA Manager",
        RoutingRoute.CM: "Collection Manager",
        RoutingRoute.CLARIFICATION: "Requester",
    }[route]
