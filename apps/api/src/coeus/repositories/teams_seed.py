"""Seed the organisational teams and member profiles from the seed users."""

from uuid import UUID, uuid4

from coeus.domain.teams import OrgTeam, TeamKind, UserProfile, team_member_ids
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.teams import TeamRepository

# (name, kind, capability team soft link, manager usernames, member usernames)
_TEAM_SPECS: tuple[tuple[str, TeamKind, str | None, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "RFA Assessment Team",
        TeamKind.RFA,
        "RFA-MARITIME",
        ("rfa.manager@example.test",),
        (
            "rfa.team@example.test",
            "analyst@example.test",
            "analyst.maritime@example.test",
            "analyst.cyber@example.test",
            "analyst.geo@example.test",
        ),
    ),
    (
        "Collection Management Team",
        TeamKind.CM,
        "CM-CYBER-SENSOR",
        ("collection.manager@example.test",),
        ("collection.team@example.test", "analyst@example.test"),
    ),
    (
        "JIOC Routing Cell",
        TeamKind.JIOC,
        None,
        (),
        ("jioc.team@example.test",),
    ),
    (
        "Quality Control Cell",
        TeamKind.QC,
        None,
        ("qc.manager@example.test",),
        (),
    ),
)


def seed_teams(teams: TeamRepository, users: SeedUserRepository) -> None:
    """Create the seed teams and empty profiles once per fresh store."""
    if teams.list_teams():
        _ensure_profiles(teams, users)
        return
    for name, kind, capability_team_id, manager_names, member_names in _TEAM_SPECS:
        managers = _user_ids(users, manager_names)
        members = _user_ids(users, member_names)
        teams.save_team(
            OrgTeam(
                team_id=uuid4(),
                name=name,
                kind=kind,
                manager_user_ids=managers,
                member_user_ids=members,
                capability_team_id=capability_team_id,
            )
        )
    _ensure_profiles(teams, users)


def _ensure_profiles(teams: TeamRepository, users: SeedUserRepository) -> None:
    """Every individual on a team gets a profile record."""
    for team in teams.list_teams():
        for user_id in sorted(team_member_ids(team), key=str):
            if teams.get_profile(user_id) is None:
                user = users.get_by_id(user_id)
                title = user.display_name if user is not None else ""
                teams.save_profile(UserProfile(user_id=user_id, title=title))


def _user_ids(users: SeedUserRepository, usernames: tuple[str, ...]) -> tuple[UUID, ...]:
    ids: list[UUID] = []
    for username in usernames:
        user = users.get_by_username(username)
        if user is not None:
            ids.append(user.user_id)
    return tuple(ids)
