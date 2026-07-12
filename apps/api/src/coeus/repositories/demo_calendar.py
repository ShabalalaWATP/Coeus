"""Deterministic team calendar demo entries (MOCK DATA ONLY, local only).

Spreads availability across each seed team's members over the coming days so
the My Team availability tiles and assignment-panel counts look realistic,
including block entries (a course and a leave block) so the month view has
multi-day ranges to show.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from coeus.domain.teams import CalendarStatus, OrgTeam, TeamCalendarEntry, team_member_ids
from coeus.repositories.access import stable_seed_id

# One status per (member offset, day offset) so the pattern looks varied but
# is fully deterministic.
_STATUS_CYCLE = (
    CalendarStatus.ON_TASK,
    CalendarStatus.AVAILABLE,
    CalendarStatus.COURSE,
    CalendarStatus.ON_TASK,
    CalendarStatus.LEAVE,
    CalendarStatus.AVAILABLE,
    CalendarStatus.APPOINTMENT,
)
_DAY_SPAN = 5
_NOTES = {
    CalendarStatus.ON_TASK: "Assigned to a live task.",
    CalendarStatus.LEAVE: "Planned leave.",
    CalendarStatus.COURSE: "Attending a training course.",
    CalendarStatus.APPOINTMENT: "Medical appointment.",
    CalendarStatus.DUTY: "Duty travel.",
    CalendarStatus.OTHER: "Blocked out.",
}


def build_demo_calendar(teams: tuple[OrgTeam, ...]) -> tuple[TeamCalendarEntry, ...]:
    today = datetime.now(UTC).date()
    entries: list[TeamCalendarEntry] = []
    for team in teams:
        members = sorted(team_member_ids(team), key=str)
        for member_index, user_id in enumerate(members):
            for day_offset in range(_DAY_SPAN):
                status = _STATUS_CYCLE[(member_index + day_offset) % len(_STATUS_CYCLE)]
                if status == CalendarStatus.AVAILABLE:
                    continue
                entry_date = today + timedelta(days=day_offset)
                entries.append(_entry(team, user_id, entry_date, status))
        # One block entry per team so the calendar shows multi-day ranges:
        # the first member is away on a course next week.
        if members:
            entries.append(
                _entry(
                    team,
                    members[0],
                    today + timedelta(days=7),
                    CalendarStatus.COURSE,
                    end_date=today + timedelta(days=10),
                )
            )
    return tuple(entries)


def _entry(
    team: OrgTeam,
    user_id: UUID,
    entry_date: date,
    status: CalendarStatus,
    end_date: date | None = None,
) -> TeamCalendarEntry:
    key = f"demo-cal-{team.team_id}-{user_id}-{entry_date.isoformat()}"
    return TeamCalendarEntry(
        entry_id=stable_seed_id(key),
        team_id=team.team_id,
        user_id=user_id,
        entry_date=entry_date.isoformat(),
        status=status,
        note=_NOTES.get(status, "Blocked out."),
        end_date=end_date.isoformat() if end_date else "",
        created_by_user_id=user_id,
    )
