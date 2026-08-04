"""Seed the organisational teams and member profiles from the seed users."""

from dataclasses import replace
from uuid import UUID

from coeus.domain.teams import OrgTeam, TeamKind, UserProfile
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.auth_seed import canonical_seed_username
from coeus.repositories.synthetic_workforce import synthetic_team_id
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
            "analyst.3@example.test",
            "analyst.16@example.test",
            "analyst.17@example.test",
        ),
    ),
    (
        "All-source and Land Assessment",
        TeamKind.RFA,
        "RFA-ALL-SOURCE-LAND",
        ("rfa.lead.2@example.test",),
        (
            "analyst.5@example.test",
            "analyst.6@example.test",
            "analyst.7@example.test",
            "analyst.15@example.test",
        ),
    ),
    (
        "Cyber and Technical Assessment",
        TeamKind.RFA,
        "RFA-CYBER-TECHNICAL",
        ("rfa.lead.3@example.test",),
        (
            "analyst.8@example.test",
            "analyst.9@example.test",
            "analyst.10@example.test",
            "analyst.14@example.test",
        ),
    ),
    (
        "Regional and Open-source Assessment",
        TeamKind.RFA,
        "RFA-REGIONAL-OSINT",
        ("rfa.lead.4@example.test",),
        (
            "analyst.11@example.test",
            "analyst.12@example.test",
            "analyst.13@example.test",
        ),
    ),
    (
        "Geospatial Collection",
        TeamKind.CM,
        "CM-GEOSPATIAL",
        ("cm.lead.2@example.test",),
        (
            "analyst.18@example.test",
            "analyst.19@example.test",
            "analyst.20@example.test",
            "analyst.24@example.test",
        ),
    ),
    (
        "Collection Requirements and Coordination",
        TeamKind.CM,
        "CM-REQUIREMENTS",
        ("cm.lead.3@example.test",),
        (
            "analyst.21@example.test",
            "analyst.22@example.test",
            "analyst.23@example.test",
        ),
    ),
    (
        "JIOC Routing Cell",
        TeamKind.JIOC,
        None,
        ("jioc.team@example.test",),
        ("jioc.member@example.test",),
    ),
    (
        "Quality Control Cell",
        TeamKind.QC,
        None,
        ("qc.manager@example.test",),
        (),
    ),
)

# Exact pre-single-home signatures. Only these untouched records are
# reconciled; any manager, member, capability, state or name edit is retained.
_LEGACY_ROUTE_TEAM_SPECS = (
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
        (
            "rfa.team@example.test",
            "analyst@example.test",
            "analyst.2@example.test",
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
        (
            "collection.team@example.test",
            "analyst.3@example.test",
            "analyst.16@example.test",
            "analyst.17@example.test",
        ),
    ),
)


def seed_teams(teams: TeamRepository, users: SeedUserRepository) -> None:
    """Create seed teams and reconcile untouched synthetic profiles."""
    if teams.list_teams():
        _reconcile_untouched_route_teams(teams, users)
        _ensure_jioc_seed_member(teams, users)
        _ensure_profiles(teams, users)
        return
    for name, kind, capability_team_id, manager_names, member_names in _TEAM_SPECS:
        managers = _user_ids(users, manager_names)
        members = _user_ids(users, member_names)
        teams.save_team(
            OrgTeam(
                team_id=synthetic_team_id(name),
                name=name,
                kind=kind,
                manager_user_ids=managers,
                member_user_ids=members,
                capability_team_id=capability_team_id,
            )
        )
    _ensure_profiles(teams, users)


def _reconcile_untouched_route_teams(teams: TeamRepository, users: SeedUserRepository) -> None:
    for (
        name,
        kind,
        capability_team_id,
        manager_names,
        legacy_member_names,
        current_member_names,
    ) in _LEGACY_ROUTE_TEAM_SPECS:
        managers = _user_ids(users, manager_names)
        legacy_members = _user_ids(users, legacy_member_names)
        current_members = _user_ids(users, current_member_names)
        for team in teams.list_teams():
            if (
                team.name == name
                and team.kind is kind
                and team.capability_team_id == capability_team_id
                and team.manager_user_ids == managers
                and team.member_user_ids == legacy_members
                and team.is_active
            ):
                teams.save_team(replace(team, member_user_ids=current_members))
                break


def _ensure_jioc_seed_member(teams: TeamRepository, users: SeedUserRepository) -> None:
    """Upgrade only the untouched pre-Team-Member synthetic JIOC cell."""
    user_ids = {canonical_seed_username(user.username): user.user_id for user in users.list_users()}
    manager_id = user_ids.get("jioc.team@example.test")
    member_id = user_ids.get("jioc.member@example.test")
    if manager_id is None or member_id is None:
        return
    for team in teams.list_teams():
        if (
            team.name == "JIOC Routing Cell"
            and team.kind is TeamKind.JIOC
            and team.capability_team_id is None
            and not team.manager_user_ids
            and team.member_user_ids == (manager_id,)
        ):
            teams.save_team(
                replace(
                    team,
                    manager_user_ids=(manager_id,),
                    member_user_ids=(member_id,),
                )
            )
            return


def _ensure_profiles(teams: TeamRepository, users: SeedUserRepository) -> None:
    """Every seed user gets a personal profile.

    Existing profiles are upgraded only while still at the bare default
    (display-name title, no specialisms, no bio), so edits made by real
    users are never overwritten on restart.
    """
    for user in users.list_users():
        canonical_username = canonical_seed_username(user.username)
        spec = PROFILE_SPECS.get(canonical_username)
        existing = teams.get_profile(user.user_id)
        if spec is None:
            if existing is None:
                teams.save_profile(UserProfile(user_id=user.user_id, title=user.display_name))
            continue
        legacy = LEGACY_PROFILE_SPECS.get(canonical_username)
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
    resolver = getattr(users, "get_seed_by_canonical_username", None)
    by_canonical = {canonical_seed_username(user.username): user for user in users.list_users()}
    ids: list[UUID] = []
    for username in usernames:
        user = resolver(username) if callable(resolver) else by_canonical.get(username)
        if user is not None:
            ids.append(user.user_id)
    return tuple(ids)
