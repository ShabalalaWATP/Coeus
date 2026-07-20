"""Shared route and selected-team authority for RFA and CM managers."""

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.teams import TeamKind
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.repositories.teams import TeamRepository

ROUTE_MANAGER_ROLES = {
    RoutingRoute.RFA: RoleName.RFA_MANAGER,
    RoutingRoute.CM: RoleName.COLLECTION_MANAGER,
}
ROUTE_MANAGER_PERMISSIONS = {
    RoutingRoute.RFA: Permission.RFA_REVIEW,
    RoutingRoute.CM: Permission.COLLECTION_REVIEW,
}


def require_route_manager(actor: UserAccount, route: RoutingRoute) -> None:
    role = ROUTE_MANAGER_ROLES.get(route)
    permission = ROUTE_MANAGER_PERMISSIONS.get(route)
    if role not in actor.roles or permission not in actor.permissions:
        raise AppError(403, "forbidden", "Permission denied.")


def require_valid_assignment_team(
    ticket: TicketRecord, route: RoutingRoute, teams: TeamRepository
) -> None:
    expected_kind = TeamKind.RFA if route == RoutingRoute.RFA else TeamKind.CM
    team_ids = {
        assignment.team_id
        for assignment in ticket.analyst_assignments
        if assignment.active and assignment.route == route and assignment.team_id is not None
    }
    if len(team_ids) > 1:
        raise AppError(409, "assignment_team_invalid", "Assignment has conflicting teams.")
    if not team_ids:
        raise AppError(409, "assignment_team_invalid", "Assignment team is not valid.")
    team = teams.get_team(next(iter(team_ids)))
    if team is None or not team.is_active or team.kind != expected_kind:
        raise AppError(409, "assignment_team_invalid", "Assignment team is no longer valid.")
