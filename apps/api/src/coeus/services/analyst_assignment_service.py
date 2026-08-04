"""Analyst assignment by the owning team manager.

Split from the analyst workflow service: assignment is a manager action on
the team queue, while the workflow service covers the analyst's own work.
Supports assigning one to five analysts; reassignment deactivates the
route's previous assignments instead of overwriting them.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.assignment_recommendations import AssignmentRecommendationAcceptance
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.domain.teams import OrgTeam, TeamKind, team_member_ids
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.repositories.access import AccessRepository
from coeus.repositories.teams import TeamRepository
from coeus.services.analyst_assignment import assignment_change
from coeus.services.analyst_records import active_assignments_for_route, approved_route
from coeus.services.audit import AuditLog
from coeus.services.team_availability import (
    TeamAvailabilityService,
)
from coeus.services.tickets import TicketServices
from coeus.services.workforce_authority import (
    PROCESS_WORKFORCE_AUTHORITY,
    WorkforceAuthority,
)

ASSIGNMENT_READ_PERMISSIONS = frozenset({Permission.RFA_ASSIGN, Permission.COLLECTION_ASSIGN})
MAX_ANALYSTS_PER_ASSIGNMENT = 5


class AnalystAssignmentService:
    def __init__(
        self,
        tickets: TicketServices,
        access_repository: AccessRepository,
        team_repository: TeamRepository,
        audit_log: AuditLog,
        availability: TeamAvailabilityService,
        workforce_authority: WorkforceAuthority = PROCESS_WORKFORCE_AUTHORITY,
    ) -> None:
        self._tickets = tickets
        self._access = access_repository
        self._teams = team_repository
        self._audit_log = audit_log
        self._availability = availability
        self._workforce_authority = workforce_authority

    def analyst_candidates(
        self, actor: UserAccount, route: RoutingRoute, team_id: UUID | None = None
    ) -> tuple[UserAccount, ...]:
        team = self._resolve_assignment_team(actor, route, team_id)
        eligible_ids = self._available_analyst_ids(team)
        return tuple(
            user
            for user in self._access.list_users()
            if user.user_id in eligible_ids
            and user.is_active
            and RoleName.INTELLIGENCE_ANALYST in user.roles
        )

    def recommendation_candidate_accounts(
        self,
        actor: UserAccount,
        route: RoutingRoute,
        team_id: UUID,
        analyst_user_ids: tuple[UUID, ...],
    ) -> tuple[UserAccount, ...]:
        """Resolve manager-visible labels without changing recommendation truth."""
        team = self.assignment_team(actor, route, team_id)
        analysts = self._resolve_analysts(analyst_user_ids)
        roster = team_member_ids(team)
        if any(analyst.user_id not in roster for analyst in analysts):
            raise AppError(409, "assignment_candidate_ineligible", "Candidate roster changed.")
        return analysts

    def assignment_teams(self, actor: UserAccount, route: RoutingRoute) -> tuple[OrgTeam, ...]:
        self._require_assignment_permission(actor, route)
        kind = self._team_kind(route)
        return tuple(
            team
            for team in self._teams.list_teams()
            if team.kind == kind and team.is_active and self._can_manage_team(actor, team)
        )

    def assignment_team(self, actor: UserAccount, route: RoutingRoute, team_id: UUID) -> OrgTeam:
        self._require_assignment_permission(actor, route)
        team = self._teams.get_team(team_id)
        if (
            team is None
            or not team.is_active
            or team.kind != self._team_kind(route)
            or not self._can_manage_team(actor, team)
        ):
            raise AppError(404, "assignment_team_not_found", "Assignment team was not found.")
        return team

    def assign(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        analyst_user_ids: tuple[UUID, ...],
        work_package_titles: tuple[str, ...],
        team_id: UUID | None = None,
        *,
        recommendation: AssignmentRecommendationAcceptance | None = None,
    ) -> TicketRecord:
        with self._workforce_authority.locked():
            return self._assign_locked(
                actor,
                ticket_id,
                analyst_user_ids,
                work_package_titles,
                team_id,
                recommendation,
            )

    def _assign_locked(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        analyst_user_ids: tuple[UUID, ...],
        work_package_titles: tuple[str, ...],
        team_id: UUID | None,
        recommendation: AssignmentRecommendationAcceptance | None = None,
    ) -> TicketRecord:
        self._require_any(actor, ASSIGNMENT_READ_PERMISSIONS)
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ASSIGNMENT_READ_PERMISSIONS
        )
        # Managers may reassign in-progress or rework tickets, e.g. after an
        # analyst account is deactivated; the ticket state does not change.
        reassignment = ticket.state in {
            TicketState.ANALYST_IN_PROGRESS,
            TicketState.REWORK_REQUIRED,
        }
        if ticket.state != TicketState.ANALYST_ASSIGNMENT and not reassignment:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting assignment.")
        route = approved_route(ticket)
        if route is None:
            raise AppError(409, "route_not_approved", "Ticket has no approved route.")
        # Only an active assignment on the current route blocks a fresh
        # assignment: the RFA follow-up leg of an analysed collect must not be
        # blocked by the completed CM leg's assignment history.
        if not reassignment and active_assignments_for_route(ticket, route):
            raise AppError(409, "analyst_already_assigned", "Ticket already has an analyst.")
        self._require_assignment_permission(actor, route)
        current_team_id = self._reassignment_team_id(actor, ticket, route) if reassignment else None
        team = self._resolve_assignment_team(actor, route, team_id)
        if (
            current_team_id is not None
            and Permission.ROLE_MANAGE not in actor.permissions
            and team.team_id != current_team_id
        ):
            raise AppError(
                403,
                "reassignment_team_change_forbidden",
                "Only an administrator can move an active assignment between teams.",
            )
        analysts = self._resolve_analysts(analyst_user_ids)
        roster_ids = team_member_ids(team)
        if any(analyst.user_id not in roster_ids for analyst in analysts):
            raise AppError(403, "analyst_outside_team", "Analysts must belong to your route team.")
        eligible_ids = self._eligible_analyst_ids(team)
        if any(analyst.user_id not in eligible_ids for analyst in analysts):
            raise AppError(
                409,
                "analyst_not_assignment_eligible",
                "Analysts must have this team as their only active team.",
            )
        available_ids = (
            self._available_analyst_ids(
                team, exclude_ticket_id=ticket.ticket_id if reassignment else None
            )
            if recommendation is None
            else eligible_ids
        )
        if any(analyst.user_id not in available_ids for analyst in analysts):
            raise AppError(
                409,
                "analyst_unavailable",
                "Analysts with leave, commitments or other live work cannot be assigned.",
            )
        if not reassignment:
            self._ensure_transition(ticket.state, TicketState.ANALYST_IN_PROGRESS)
        change = assignment_change(
            ticket,
            actor,
            analysts,
            route,
            work_package_titles,
            team.team_id,
            team.name,
            reassignment=reassignment,
        )
        if recommendation is not None:
            change.audit_metadata["recommendation_id"] = str(recommendation.recommendation_id)
            change.audit_metadata["recommendation_decision"] = (
                "soft_override" if recommendation.override_reason else "accepted"
            )
        return self._tickets.mutations.save_assignment_if_current(
            ticket,
            change.ticket,
            actor,
            change.event_type,
            change.audit_metadata,
            AssignmentOwnershipIntent(
                owning_unit_id=team.team_id,
                workflow_leg=(
                    WorkflowLeg.RFA if route is RoutingRoute.RFA else WorkflowLeg.CM_COLLECTION
                ),
                manager_user_id=actor.user_id,
                history_reference=change.ticket.timeline[-1].entry_id,
                target_date=_target_date(ticket),
            ),
            recommendation,
        )

    def _reassignment_team_id(
        self, actor: UserAccount, ticket: TicketRecord, route: RoutingRoute
    ) -> UUID:
        assignments = active_assignments_for_route(ticket, route)
        team_ids = {assignment.team_id for assignment in assignments}
        if len(team_ids) != 1 or None in team_ids:
            raise AppError(
                409,
                "assignment_team_ambiguous",
                "The current assignment team cannot be determined safely.",
            )
        current_team_id = next(iter(team_ids))
        assert current_team_id is not None
        current_team = self._teams.get_team(current_team_id)
        if (
            current_team is None
            or not current_team.is_active
            or current_team.kind is not self._team_kind(route)
        ):
            raise AppError(
                409,
                "assignment_team_unavailable",
                "The current assignment team is not active.",
            )
        if (
            Permission.ROLE_MANAGE not in actor.permissions
            and actor.user_id not in current_team.manager_user_ids
        ):
            raise AppError(
                403,
                "reassignment_team_forbidden",
                "Only a manager of the current assignment team can reassign this ticket.",
            )
        return current_team_id

    def _resolve_analysts(self, analyst_user_ids: tuple[UUID, ...]) -> tuple[UserAccount, ...]:
        unique_ids = tuple(dict.fromkeys(analyst_user_ids))
        if not unique_ids or len(unique_ids) > MAX_ANALYSTS_PER_ASSIGNMENT:
            raise AppError(422, "invalid_analyst", "Assign between one and five distinct analysts.")
        analysts: list[UserAccount] = []
        for analyst_user_id in unique_ids:
            analyst = self._access.get_user(analyst_user_id)
            if (
                analyst is None
                or not analyst.is_active
                or RoleName.INTELLIGENCE_ANALYST not in analyst.roles
            ):
                raise AppError(422, "invalid_analyst", "Assigned user must be an active analyst.")
            analysts.append(analyst)
        return tuple(analysts)

    def _resolve_assignment_team(
        self, actor: UserAccount, route: RoutingRoute, team_id: UUID | None
    ) -> OrgTeam:
        if team_id is not None:
            return self.assignment_team(actor, route, team_id)
        teams = self.assignment_teams(actor, route)
        if len(teams) != 1:
            raise AppError(422, "assignment_team_required", "Select an assignment team.")
        return teams[0]

    def _eligible_analyst_ids(self, team: OrgTeam) -> frozenset[UUID]:
        return self._availability.assignable_member_ids(team)

    def _available_analyst_ids(
        self, team: OrgTeam, exclude_ticket_id: UUID | None = None
    ) -> frozenset[UUID]:
        today = datetime.now(UTC).date().isoformat()
        return self._availability.available_member_ids(
            team, today, exclude_ticket_id=exclude_ticket_id
        )

    @staticmethod
    def _can_manage_team(actor: UserAccount, team: OrgTeam) -> bool:
        return Permission.ROLE_MANAGE in actor.permissions or actor.user_id in team.manager_user_ids

    @staticmethod
    def _require_any(actor: UserAccount, permissions: frozenset[Permission]) -> None:
        if not permissions.intersection(actor.permissions):
            raise AppError(403, "forbidden", "Permission denied.")

    def _require_assignment_permission(self, actor: UserAccount, route: RoutingRoute) -> None:
        permission = (
            Permission.RFA_ASSIGN if route == RoutingRoute.RFA else Permission.COLLECTION_ASSIGN
        )
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def _team_kind(route: RoutingRoute) -> TeamKind:
        return TeamKind.RFA if route == RoutingRoute.RFA else TeamKind.CM

    @staticmethod
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")


def _target_date(ticket: TicketRecord) -> date | None:
    value = ticket.intake.deadline if ticket.intake is not None else None
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None
