"""Human-reviewed assignment recommendation application service."""

from datetime import UTC, datetime, time
from uuid import UUID

from coeus.application.ports.assignment_recommendations import AssignmentRecommendationStore
from coeus.core.errors import AppError
from coeus.domain.assignment_recommendations import (
    AcceptRecommendationRequest,
    AssignmentDemand,
    AssignmentRecommendationConflict,
    AssignmentRecommendationDenied,
    AssignmentRecommendationPreview,
    PrepareRecommendationRequest,
)
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.services.analyst_assignment_service import (
    ASSIGNMENT_READ_PERMISSIONS,
    AnalystAssignmentService,
)
from coeus.services.analyst_records import active_assignments_for_route, approved_route
from coeus.services.tickets import TicketServices


class AssignmentRecommendationService:
    def __init__(
        self,
        tickets: TicketServices,
        assignments: AnalystAssignmentService,
        store: AssignmentRecommendationStore,
    ) -> None:
        self._tickets = tickets
        self._assignments = assignments
        self._store = store

    def preview(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        effort_min_minutes: int,
        effort_max_minutes: int,
        deadline: datetime,
        capability_ids: tuple[str, ...],
        unit_id: UUID | None,
    ) -> AssignmentRecommendationPreview:
        ticket, route = self._context(actor, ticket_id)
        if unit_id is None:
            if not self._assignments.assignment_teams(actor, route):
                raise AppError(403, "forbidden", "Permission denied.")
        else:
            self._assignments.assignment_team(actor, route, unit_id)
        now = datetime.now(UTC)
        bounded_deadline = _bounded_deadline(ticket, deadline)
        try:
            return self._store.prepare(
                actor.user_id,
                PrepareRecommendationRequest(
                    AssignmentDemand(
                        ticket_id,
                        _workflow_leg(route),
                        effort_min_minutes,
                        effort_max_minutes,
                        now,
                        bounded_deadline,
                        tuple(dict.fromkeys(value.strip() for value in capability_ids)),
                    ),
                    unit_id,
                ),
            )
        except AssignmentRecommendationDenied as exc:
            raise AppError(
                409,
                "assignment_recommendation_unavailable",
                "No safe assignment recommendation is currently available.",
            ) from exc
        except ValueError as exc:
            raise AppError(
                422,
                "invalid_assignment_demand",
                "The effort, capabilities or deadline are invalid.",
            ) from exc

    def accept(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        request: AcceptRecommendationRequest,
        work_package_titles: tuple[str, ...],
    ) -> TicketRecord:
        self._context(actor, ticket_id)
        try:
            acceptance = self._store.acceptance(actor.user_id, request)
            return self._assignments.assign(
                actor,
                ticket_id,
                (acceptance.selected_analyst_user_id,),
                work_package_titles,
                acceptance.selected_unit_id,
                recommendation=acceptance,
            )
        except AssignmentRecommendationConflict as exc:
            raise AppError(
                409,
                "assignment_recommendation_changed",
                "The recommendation changed or expired. Preview it again.",
            ) from exc
        except AssignmentRecommendationDenied as exc:
            raise AppError(
                409,
                "assignment_candidate_ineligible",
                "The selected candidate is no longer eligible. Preview again.",
            ) from exc

    def candidate_display_names(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        preview: AssignmentRecommendationPreview,
    ) -> dict[UUID, str]:
        _, route = self._context(actor, ticket_id)
        values: dict[UUID, str] = {}
        for unit_id in sorted({item.unit_id for item in preview.candidates}, key=str):
            ids = tuple(
                item.analyst_user_id for item in preview.candidates if item.unit_id == unit_id
            )
            for account in self._assignments.recommendation_candidate_accounts(
                actor, route, unit_id, ids
            ):
                values[account.user_id] = account.display_name
        return values

    def _context(self, actor: UserAccount, ticket_id: UUID) -> tuple[TicketRecord, RoutingRoute]:
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ASSIGNMENT_READ_PERMISSIONS
        )
        if ticket.state is not TicketState.ANALYST_ASSIGNMENT:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting assignment.")
        route = approved_route(ticket)
        if route is None:
            raise AppError(409, "route_not_approved", "Ticket has no approved route.")
        if active_assignments_for_route(ticket, route):
            raise AppError(409, "analyst_already_assigned", "Ticket already has an analyst.")
        return ticket, route


def _workflow_leg(route: RoutingRoute) -> WorkflowLeg:
    return WorkflowLeg.RFA if route is RoutingRoute.RFA else WorkflowLeg.CM_COLLECTION


def _bounded_deadline(ticket: TicketRecord, requested: datetime) -> datetime:
    """Cap the requested deadline by the customer's, when theirs is machine-readable.

    Intake deadlines are free text, so many tickets carry values such as
    "Friday". There is nothing to cap against then, and the ticket can no longer
    be edited at assignment time, so the manager's own validated deadline stands.
    """
    if requested.tzinfo is None:
        raise AppError(422, "invalid_deadline", "The assignment deadline needs a time zone.")
    value = ticket.intake.deadline if ticket.intake is not None else None
    if not value:
        return requested.astimezone(UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return requested.astimezone(UTC)
    if parsed.tzinfo is None:
        parsed = datetime.combine(parsed.date(), time.max, UTC)
    return min(requested.astimezone(UTC), parsed.astimezone(UTC))
