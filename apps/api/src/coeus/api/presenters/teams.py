from coeus.domain.auth import UserAccount
from coeus.domain.teams import OrgTeam, TeamCalendarEntry, UserProfile, entry_end
from coeus.repositories.teams import TeamRepository
from coeus.schemas.teams import (
    AvailabilityResponse,
    CalendarEntryResponse,
    ProfileResponse,
    TeamMemberResponse,
    TeamResponse,
)
from coeus.services.team_availability import TeamAvailability


def team_response(
    team: OrgTeam, roster: tuple[UserAccount, ...], teams: TeamRepository
) -> TeamResponse:
    return TeamResponse(
        team_id=team.team_id,
        name=team.name,
        kind=team.kind.value,
        capability_team_id=team.capability_team_id,
        members=[_member_response(team, member, teams) for member in roster],
    )


def _member_response(
    team: OrgTeam, member: UserAccount, teams: TeamRepository
) -> TeamMemberResponse:
    profile = teams.get_profile(member.user_id)
    return TeamMemberResponse(
        user_id=member.user_id,
        username=member.username,
        display_name=member.display_name,
        is_manager=member.user_id in team.manager_user_ids,
        title=profile.title if profile else "",
        specialisms=list(profile.specialisms) if profile else [],
        bio=profile.bio if profile else "",
    )


def calendar_entry_response(entry: TeamCalendarEntry) -> CalendarEntryResponse:
    return CalendarEntryResponse(
        entry_id=entry.entry_id,
        user_id=entry.user_id,
        entry_date=entry.entry_date,
        end_date=entry_end(entry),
        status=entry.status.value,
        note=entry.note,
        created_by_user_id=entry.created_by_user_id,
    )


def availability_response(availability: TeamAvailability) -> AvailabilityResponse:
    return AvailabilityResponse(
        team_id=availability.team_id,
        entry_date=availability.entry_date,
        members=availability.members,
        on_leave=availability.on_leave,
        on_task_calendar=availability.on_task_calendar,
        other_commitments=availability.other_commitments,
        assigned_live=availability.assigned_live,
        on_task=availability.on_task,
        free=availability.free,
    )


def profile_response(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        user_id=profile.user_id,
        title=profile.title,
        specialisms=list(profile.specialisms),
        bio=profile.bio,
        updated_at=profile.updated_at,
    )
