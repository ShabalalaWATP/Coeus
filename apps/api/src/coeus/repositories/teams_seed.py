"""Seed the organisational teams and member profiles from the seed users."""

from uuid import UUID, uuid4

from coeus.domain.teams import OrgTeam, TeamKind, UserProfile
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.teams import TeamRepository
from coeus.repositories.teams_seed_profiles import LEGACY_PROFILE_SPECS, PROFILE_SPECS

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
            "analyst.2@example.test",
            "analyst.3@example.test",
            "analyst.4@example.test",
        ),
    ),
    (
        "Collection Management Team",
        TeamKind.CM,
        "CM-CYBER-SENSOR",
        ("collection.manager@example.test",),
        (
            "collection.team@example.test",
            "analyst@example.test",
            "analyst.3@example.test",
        ),
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
    """Create seed teams and reconcile untouched synthetic profiles."""
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
    """Every seed user gets a personal profile.

    Existing profiles are upgraded only while still at the bare default
    (display-name title, no specialisms, no bio), so edits made by real
    users are never overwritten on restart.
    """
    for user in users.list_users():
        spec = PROFILE_SPECS.get(user.username)
        existing = teams.get_profile(user.user_id)
        if spec is None:
            if existing is None:
                teams.save_profile(UserProfile(user_id=user.user_id, title=user.display_name))
            continue
        legacy = LEGACY_PROFILE_SPECS.get(user.username)
        if existing is not None and not _matches_profile(existing, legacy):
            continue
        title, specialisms, bio = spec
        teams.save_profile(
            UserProfile(user_id=user.user_id, title=title, specialisms=specialisms, bio=bio)
        )


def _matches_profile(profile: UserProfile, spec: tuple[str, tuple[str, ...], str] | None) -> bool:
    if spec is None:
        return False
    title, specialisms, bio = spec
    return (profile.title, profile.specialisms, profile.bio) == (title, specialisms, bio)


def _user_ids(users: SeedUserRepository, usernames: tuple[str, ...]) -> tuple[UUID, ...]:
    ids: list[UUID] = []
    for username in usernames:
        user = users.get_by_username(username)
        if user is not None:
            ids.append(user.user_id)
    return tuple(ids)
