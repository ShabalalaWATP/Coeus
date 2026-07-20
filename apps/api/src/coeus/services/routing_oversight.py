"""Bounded read-only JIOC projection across workflow and area teams."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.teams import OrgTeam, TeamKind, team_member_ids
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.repositories.access import AccessRepository
from coeus.repositories.teams import TeamRepository
from coeus.services.analyst_records import active_assignments, approved_route
from coeus.services.analyst_workflow import VISIBLE_ANALYST_STATES
from coeus.services.team_availability import TeamAvailabilityService
from coeus.services.tickets import TicketServices

OVERSIGHT_TASK_LIMIT = 200
OVERSIGHT_TEAM_LIMIT = 50
OVERSIGHT_ANALYST_LIMIT = 200


@dataclass(frozen=True)
class OversightTeam:
    team_id: UUID
    name: str
    kind: str
    active_members: int
    available_members: int
    live_task_count: int


@dataclass(frozen=True)
class OversightAnalyst:
    user_id: UUID
    display_name: str
    team_ids: tuple[UUID, ...]
    live_task_count: int


@dataclass(frozen=True)
class OversightTask:
    ticket_id: UUID
    reference: str
    state: str
    route: str | None
    team_id: UUID | None
    team_name: str | None
    analyst_count: int
    work_package_count: int
    completed_work_package_count: int
    agent_disposition: str | None
    agent_confidence: float | None


@dataclass(frozen=True)
class RoutingOversight:
    counts_by_state: tuple[tuple[str, int], ...]
    counts_by_route: tuple[tuple[str, int], ...]
    teams: tuple[OversightTeam, ...]
    analysts: tuple[OversightAnalyst, ...]
    tasks: tuple[OversightTask, ...]


class RoutingOversightService:
    def __init__(
        self,
        tickets: TicketServices,
        teams: TeamRepository,
        access: AccessRepository,
        availability: TeamAvailabilityService,
    ) -> None:
        self._tickets = tickets
        self._teams = teams
        self._access = access
        self._availability = availability

    def view(self, actor: UserAccount) -> RoutingOversight:
        if Permission.JIOC_OVERSIGHT not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        tickets = self._tickets.tickets.assignment_snapshot()
        state_counts = Counter(ticket.state.value for ticket in tickets)
        route_counts = Counter(
            route.value for ticket in tickets if (route := approved_route(ticket)) is not None
        )
        active_teams = tuple(
            team
            for team in self._teams.list_teams()
            if team.is_active and team.kind in {TeamKind.RFA, TeamKind.CM}
        )[:OVERSIGHT_TEAM_LIMIT]
        live_tickets = tuple(ticket for ticket in tickets if ticket.state in VISIBLE_ANALYST_STATES)
        task_counts = Counter(
            assignment.team_id
            for ticket in live_tickets
            for assignment in active_assignments(ticket)
            if assignment.team_id is not None
        )
        today = datetime.now().astimezone().date().isoformat()
        teams = tuple(
            OversightTeam(
                team.team_id,
                team.name,
                team.kind.value,
                len(self._active_members(team_member_ids(team))),
                self._availability.availability(team, today).free,
                task_counts[team.team_id],
            )
            for team in active_teams
        )
        analysts = self._analysts(active_teams, live_tickets)
        selected = sorted(tickets, key=lambda ticket: ticket.updated_at, reverse=True)[
            :OVERSIGHT_TASK_LIMIT
        ]
        return RoutingOversight(
            tuple(sorted(state_counts.items())),
            tuple(sorted(route_counts.items())),
            teams,
            analysts,
            tuple(self._task(ticket) for ticket in selected),
        )

    def _active_members(self, member_ids: frozenset[UUID]) -> tuple[UserAccount, ...]:
        return tuple(
            user
            for user_id in member_ids
            if (user := self._access.get_user(user_id)) is not None and user.is_active
        )

    def _analysts(
        self, teams: tuple[OrgTeam, ...], tickets: tuple[TicketRecord, ...]
    ) -> tuple[OversightAnalyst, ...]:
        memberships: dict[UUID, list[UUID]] = {}
        for team in teams:
            for user_id in team_member_ids(team):
                memberships.setdefault(user_id, []).append(team.team_id)
        live = Counter(
            assignment.analyst_user_id
            for ticket in tickets
            for assignment in active_assignments(ticket)
        )
        result: list[OversightAnalyst] = []
        for user_id, team_ids in memberships.items():
            user = self._access.get_user(user_id)
            if user and user.is_active and RoleName.INTELLIGENCE_ANALYST in user.roles:
                result.append(
                    OversightAnalyst(
                        user_id,
                        user.display_name,
                        tuple(sorted(team_ids, key=str)),
                        live[user_id],
                    )
                )
        return tuple(
            sorted(
                result,
                key=lambda item: item.display_name.casefold(),
            )
        )[:OVERSIGHT_ANALYST_LIMIT]

    @staticmethod
    def _task(ticket: TicketRecord) -> OversightTask:
        assignments = active_assignments(ticket)
        latest = assignments[-1] if assignments else None
        route: RoutingRoute | None = approved_route(ticket)
        agent_decision = (
            ticket.jioc_routing_decisions[-1] if ticket.jioc_routing_decisions else None
        )
        return OversightTask(
            ticket.ticket_id,
            ticket.reference,
            ticket.state.value,
            route.value if route else None,
            latest.team_id if latest else None,
            latest.team_name if latest else None,
            len({assignment.analyst_user_id for assignment in assignments}),
            len(ticket.work_packages),
            sum(package.status.value == "complete" for package in ticket.work_packages),
            agent_decision.disposition if agent_decision else None,
            agent_decision.confidence if agent_decision else None,
        )
