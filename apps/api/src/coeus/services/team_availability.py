"""Deterministic team availability for a calendar date.

Combines the team calendar (self-reported availability) with live analyst
assignments on in-flight tickets, so managers see how many people are free
before assigning new work. No model involvement: pure counting.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.teams import (
    OTHER_COMMITMENT_STATUSES,
    CalendarStatus,
    OrgTeam,
    TeamCalendarEntry,
    TeamKind,
    entry_covers,
    entry_end,
    team_member_ids,
)
from coeus.repositories.teams import TeamRepository
from coeus.services.analyst_records import active_assignments
from coeus.services.audit import AuditLog
from coeus.services.tickets import TicketServices
from coeus.services.workforce_authority import (
    PROCESS_WORKFORCE_AUTHORITY,
    WorkforceAuthority,
)

# States where an active assignment still occupies the analysts.
IN_FLIGHT_STATES = frozenset(
    {
        TicketState.ANALYST_IN_PROGRESS,
        TicketState.MANAGER_APPROVAL,
        TicketState.QC_REVIEW,
        TicketState.REWORK_REQUIRED,
    }
)
MAX_CALENDAR_WINDOW_DAYS = 62
MANAGER_ROLE_BY_TEAM_KIND = {
    TeamKind.RFA: RoleName.RFA_MANAGER,
    TeamKind.CM: RoleName.COLLECTION_MANAGER,
}


@dataclass(frozen=True)
class TeamAvailability:
    team_id: UUID
    entry_date: str
    members: int
    active_people: int
    assignable: int
    on_leave: int
    on_task_calendar: int
    other_commitments: int
    assigned_live: int
    on_task: int
    free: int


class UserReader(Protocol):
    def list_users(self) -> tuple[UserAccount, ...]: ...


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise AppError(422, "invalid_date", "Dates must be ISO calendar dates.") from error


class TeamAvailabilityService:
    def __init__(
        self,
        teams: TeamRepository,
        tickets: TicketServices,
        users: UserReader,
    ) -> None:
        self._teams = teams
        self._tickets = tickets
        self._users = users

    def calendar(
        self, team: OrgTeam, date_from: str, date_to: str
    ) -> tuple[TeamCalendarEntry, ...]:
        start = parse_iso_date(date_from)
        end = parse_iso_date(date_to)
        if end < start or (end - start).days > MAX_CALENDAR_WINDOW_DAYS:
            raise AppError(422, "invalid_date", "The calendar window is invalid.")
        # Block entries are returned when their range overlaps the window.
        return tuple(
            entry
            for entry in self._teams.list_entries(team.team_id)
            if parse_iso_date(entry.entry_date) <= end and start <= parse_iso_date(entry_end(entry))
        )

    def availability(self, team: OrgTeam, entry_date: str) -> TeamAvailability:
        parse_iso_date(entry_date)
        members = team_member_ids(team)
        users = {user.user_id: user for user in self._users.list_users()}
        active_people = sum(
            1 for user_id in members if (user := users.get(user_id)) is not None and user.is_active
        )
        assignable = self.assignable_member_ids(team)
        statuses = self._calendar_statuses(team, entry_date, assignable)
        on_leave = {user for user, status in statuses.items() if status == CalendarStatus.LEAVE}
        on_task = {user for user, status in statuses.items() if status == CalendarStatus.ON_TASK}
        other = {user for user, status in statuses.items() if status in OTHER_COMMITMENT_STATUSES}
        assigned = self._assigned_members(assignable)
        busy = on_leave | on_task | other | assigned
        return TeamAvailability(
            team_id=team.team_id,
            entry_date=entry_date,
            members=len(members),
            active_people=active_people,
            assignable=len(assignable),
            on_leave=len(on_leave),
            on_task_calendar=len(on_task),
            other_commitments=len(other),
            assigned_live=len(assigned),
            on_task=len((on_task | assigned) - on_leave),
            free=len(assignable - busy),
        )

    def assignable_member_ids(self, team: OrgTeam) -> frozenset[UUID]:
        """Return active analysts whose only active team is this team.

        Legacy overlapping memberships fail closed. Managers, coordinators and
        inactive accounts remain visible on the roster but never add capacity.
        """
        if not team.is_active:
            return frozenset()
        users = self._users.list_users()
        return frozenset(
            user.user_id
            for user in users
            if user.is_active
            and RoleName.INTELLIGENCE_ANALYST in user.roles
            and user.user_id in team.member_user_ids
            and user.user_id not in team.manager_user_ids
            and active_team_ids_for_user(self._teams, user.user_id) == (team.team_id,)
        )

    def available_member_ids(
        self,
        team: OrgTeam,
        entry_date: str,
        exclude_ticket_id: UUID | None = None,
    ) -> frozenset[UUID]:
        """Return assignable analysts who have no calendar or live-work conflict."""
        parse_iso_date(entry_date)
        assignable = self.assignable_member_ids(team)
        statuses = self._calendar_statuses(team, entry_date, assignable)
        calendar_busy = {
            user_id
            for user_id, status in statuses.items()
            if status is not CalendarStatus.AVAILABLE
        }
        return (
            assignable
            - calendar_busy
            - self._assigned_members(assignable, exclude_ticket_id=exclude_ticket_id)
        )

    def _calendar_statuses(
        self, team: OrgTeam, entry_date: str, members: frozenset[UUID]
    ) -> dict[UUID, CalendarStatus]:
        statuses: dict[UUID, CalendarStatus] = {}
        # Among entries covering the date, the most recently created wins per
        # user, so a fresh single-day override beats an older block entry.
        covering = (
            entry
            for entry in self._teams.list_entries(team.team_id)
            if entry.user_id in members and entry_covers(entry, entry_date)
        )
        for entry in sorted(covering, key=lambda entry: entry.created_at):
            statuses[entry.user_id] = entry.status
        return statuses

    def _assigned_members(
        self, members: frozenset[UUID], exclude_ticket_id: UUID | None = None
    ) -> set[UUID]:
        assigned: set[UUID] = set()
        for ticket in self._tickets.tickets.assignment_snapshot():
            if exclude_ticket_id is not None and ticket.ticket_id == exclude_ticket_id:
                continue
            if ticket.state not in IN_FLIGHT_STATES:
                continue
            for assignment in active_assignments(ticket):
                if assignment.analyst_user_id in members:
                    assigned.add(assignment.analyst_user_id)
        return assigned

    def has_live_assignment(self, user_id: UUID) -> bool:
        return bool(self._assigned_members(frozenset({user_id})))


def active_team_ids_for_user(teams: TeamRepository, user_id: UUID) -> tuple[UUID, ...]:
    """Return the active teams containing a user in any roster capacity."""
    return tuple(
        team.team_id
        for team in teams.list_teams()
        if team.is_active and user_id in team_member_ids(team)
    )


def can_write_entry(actor: UserAccount, team: OrgTeam, target_user_id: UUID) -> bool:
    """Members write their own entries; the team's managers write anyone's."""
    required_role = MANAGER_ROLE_BY_TEAM_KIND.get(team.kind)
    if (
        Permission.TEAM_MANAGE in actor.permissions
        and required_role in actor.roles
        and actor.user_id in team.manager_user_ids
    ):
        return target_user_id in team_member_ids(team)
    return actor.user_id == target_user_id and actor.user_id in team_member_ids(team)


class TeamCalendarService:
    def __init__(
        self,
        teams: TeamRepository,
        audit_log: AuditLog,
        workforce_authority: WorkforceAuthority = PROCESS_WORKFORCE_AUTHORITY,
    ) -> None:
        self._teams = teams
        self._audit_log = audit_log
        self._workforce_authority = workforce_authority

    def add_entry(
        self,
        actor: UserAccount,
        team: OrgTeam,
        target_user_id: UUID,
        entry_date: str,
        status: CalendarStatus,
        note: str,
        end_date: str = "",
    ) -> TeamCalendarEntry:
        with self._workforce_authority.locked():
            return self._add_entry_locked(
                actor, team, target_user_id, entry_date, status, note, end_date
            )

    def _add_entry_locked(
        self,
        actor: UserAccount,
        team: OrgTeam,
        target_user_id: UUID,
        entry_date: str,
        status: CalendarStatus,
        note: str,
        end_date: str,
    ) -> TeamCalendarEntry:
        current_team = self._teams.get_team(team.team_id)
        if current_team is None or not current_team.is_active:
            raise AppError(404, "team_not_found", "Team was not found.")
        team = current_team
        parsed_date = parse_iso_date(entry_date)
        parsed_end = parse_iso_date(end_date) if end_date else parsed_date
        today = datetime.now(UTC).date()
        if parsed_end < parsed_date:
            raise AppError(422, "invalid_calendar_date", "The end date is before the start date.")
        if parsed_date < today:
            raise AppError(422, "invalid_calendar_date", "Calendar entries cannot be in the past.")
        if parsed_end > today + timedelta(days=MAX_CALENDAR_WINDOW_DAYS):
            raise AppError(
                422,
                "invalid_calendar_date",
                f"Calendar entries must end within the next {MAX_CALENDAR_WINDOW_DAYS} days.",
            )
        if not can_write_entry(actor, team, target_user_id):
            raise AppError(403, "forbidden", "Permission denied.")
        entry = TeamCalendarEntry(
            entry_id=uuid4(),
            team_id=team.team_id,
            user_id=target_user_id,
            entry_date=entry_date,
            status=status,
            note=note.strip(),
            end_date=end_date if parsed_end != parsed_date else "",
            created_by_user_id=actor.user_id,
        )
        self._teams.save_entry(entry)
        try:
            self._audit_log.record(
                "team_calendar_entry_added",
                str(actor.user_id),
                {
                    "team_id": str(team.team_id),
                    "user_id": str(target_user_id),
                    "date": entry_date,
                    "end_date": entry_end(entry),
                    "status": status.value,
                },
            )
        except Exception:
            self._teams.delete_entry(entry.entry_id)
            raise
        return entry

    def remove_entry(self, actor: UserAccount, team: OrgTeam, entry_id: UUID) -> None:
        with self._workforce_authority.locked():
            self._remove_entry_locked(actor, team, entry_id)

    def _remove_entry_locked(self, actor: UserAccount, team: OrgTeam, entry_id: UUID) -> None:
        current_team = self._teams.get_team(team.team_id)
        if current_team is None or not current_team.is_active:
            raise AppError(404, "team_not_found", "Team was not found.")
        team = current_team
        entry = self._teams.get_entry(entry_id)
        if entry is None or entry.team_id != team.team_id:
            raise AppError(404, "entry_not_found", "Calendar entry was not found.")
        if not can_write_entry(actor, team, entry.user_id):
            raise AppError(403, "forbidden", "Permission denied.")
        removed = self._teams.delete_entry(entry_id)
        try:
            self._audit_log.record(
                "team_calendar_entry_removed",
                str(actor.user_id),
                {"team_id": str(team.team_id), "entry_id": str(entry_id)},
            )
        except Exception:
            if removed is not None:
                self._teams.save_entry(removed)
            raise
