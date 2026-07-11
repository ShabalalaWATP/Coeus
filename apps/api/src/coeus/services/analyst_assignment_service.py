"""Analyst assignment by the owning team manager.

Split from the analyst workflow service: assignment is a manager action on
the team queue, while the workflow service covers the analyst's own work.
Supports assigning one to five analysts; reassignment deactivates the
route's previous assignments instead of overwriting them.
"""

from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.repositories.access import AccessRepository
from coeus.services.analyst_assignment import assignment_change
from coeus.services.analyst_records import active_assignments_for_route, approved_route
from coeus.services.audit import AuditLog
from coeus.services.audit_rollback import record_ticket_audit_or_rollback
from coeus.services.tickets import TicketServices

ASSIGNMENT_READ_PERMISSIONS = frozenset({Permission.RFA_ASSIGN, Permission.COLLECTION_ASSIGN})
MAX_ANALYSTS_PER_ASSIGNMENT = 5


class AnalystAssignmentService:
    def __init__(
        self,
        tickets: TicketServices,
        access_repository: AccessRepository,
        audit_log: AuditLog,
    ) -> None:
        self._tickets = tickets
        self._access = access_repository
        self._audit_log = audit_log

    def analyst_candidates(self, actor: UserAccount) -> tuple[UserAccount, ...]:
        self._require_any(actor, ASSIGNMENT_READ_PERMISSIONS)
        return tuple(
            user
            for user in self._access.list_users()
            if user.is_active and RoleName.INTELLIGENCE_ANALYST in user.roles
        )

    def assign(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        analyst_user_ids: tuple[UUID, ...],
        work_package_titles: tuple[str, ...],
        team_name: str | None = None,
    ) -> TicketRecord:
        self._require_any(actor, ASSIGNMENT_READ_PERMISSIONS)
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ASSIGNMENT_READ_PERMISSIONS
        )
        # Managers may reassign an in-progress ticket, e.g. after an analyst
        # account is deactivated; the state stays ANALYST_IN_PROGRESS.
        reassignment = ticket.state == TicketState.ANALYST_IN_PROGRESS
        if ticket.state not in {TicketState.ANALYST_ASSIGNMENT, TicketState.ANALYST_IN_PROGRESS}:
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
        analysts = self._resolve_analysts(analyst_user_ids)
        if not reassignment:
            self._ensure_transition(ticket.state, TicketState.ANALYST_IN_PROGRESS)
        change = assignment_change(
            ticket,
            actor,
            analysts,
            route,
            work_package_titles,
            team_name,
            reassignment=reassignment,
        )
        updated = self._tickets.tickets.save_system_update(change.ticket)
        record_ticket_audit_or_rollback(
            self._tickets.tickets,
            self._audit_log,
            ticket,
            change.event_type,
            actor,
            change.audit_metadata,
        )
        return updated

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
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")
