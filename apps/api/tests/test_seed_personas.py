from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.domain.auth import RoleName
from coeus.domain.teams import OrgTeam, TeamKind, UserProfile, team_member_ids
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import MemoryStateStore
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.auth_seed import NUMBERED_SEED_LOGIN_PROFILE, seed_user_specs
from coeus.repositories.teams import TeamRepository
from coeus.repositories.teams_seed import seed_teams
from coeus.repositories.teams_seed_profiles import LEGACY_PROFILE_SPECS, PROFILE_SPECS


class StaticPasswordHasher:
    def hash(self, credential: str) -> str:
        return f"synthetic-hash:{credential}"

    def verify(self, stored_hash: str, credential: str) -> bool:
        return stored_hash == self.hash(credential)

    def needs_rehash(self, stored_hash: str) -> bool:
        return False


def _users(state_store: MemoryStateStore | None = None) -> SeedUserRepository:
    return SeedUserRepository(Settings(environment="test"), StaticPasswordHasher(), state_store)


def test_seed_personas_are_unique_and_analysts_share_one_generic_role() -> None:
    users = _users()
    accounts = users.list_users()
    analysts = [user for user in accounts if user.roles == {RoleName.INTELLIGENCE_ANALYST}]

    assert len(accounts) == 53
    assert len({user.display_name for user in accounts}) == 53
    assert len(analysts) == 24
    assert {user.username for user in analysts} == {
        "analyst@example.test",
        *(f"analyst.{index}@example.test" for index in range(2, 25)),
    }
    assert all(
        PROFILE_SPECS[user.username][0] == "Military Intelligence Analyst" for user in analysts
    )
    assert all(
        PROFILE_SPECS[user.username][2].startswith("Synthetic exercise persona")
        for user in accounts
    )


def test_legacy_seed_identity_reconciliation_preserves_account_authority() -> None:
    baseline = _users()
    stored = []
    expected_ids = {}
    expected_hashes = {}
    for user in baseline.list_users():
        spec = next(item for item in seed_user_specs() if item.username == user.username)
        legacy_username = spec.legacy_usernames[0] if spec.legacy_usernames else user.username
        legacy = replace(
            user,
            username=legacy_username,
            display_name=spec.legacy_display_names[-1],
            credential_version=7,
        )
        stored.append(encode_value(legacy))
        expected_ids[spec.username] = user.user_id
        expected_hashes[spec.username] = user.password_hash

    state_store = MemoryStateStore()
    state_store.save("users", {"users": stored})
    restored = _users(state_store)

    assert len(restored.list_users()) == 53
    for spec in seed_user_specs():
        user = restored.get_by_username(spec.username)
        assert user is not None
        assert user.user_id == expected_ids[spec.username]
        assert user.display_name == spec.display_name
        assert user.credential_version == 7
        assert user.roles == spec.roles
        assert user.password_hash == expected_hashes[spec.username]
        for legacy_username in spec.legacy_usernames:
            assert restored.get_by_username(legacy_username) is None


def test_numbered_local_seed_identities_migrate_credentials_without_login_aliases() -> None:
    baseline = _users()
    state_store = MemoryStateStore()
    state_store.save(
        "users",
        {"users": [encode_value(user) for user in baseline.list_users()]},
    )
    settings = Settings(
        environment="local",
        local_numbered_seed_usernames=True,
        local_seed_credential="admin",
    )

    numbered = SeedUserRepository(settings, StaticPasswordHasher(), state_store)
    accounts = sorted(numbered.list_users(), key=lambda user: int(user.username[5:]))

    assert [user.username for user in accounts] == [f"admin{index}" for index in range(1, 54)]
    for index, spec in enumerate(seed_user_specs(), start=1):
        canonical = baseline.get_by_username(spec.username)
        renamed = numbered.get_by_username(f"admin{index}")
        assert canonical is not None and renamed is not None
        assert numbered.get_by_username(spec.username) is None
        assert numbered.get_seed_by_canonical_username(spec.username) is renamed
        assert numbered.username_is_reserved(spec.username)
        assert numbered.username_is_reserved(f"admin{index}")
        assert all(numbered.username_is_reserved(alias) for alias in spec.legacy_usernames)
        assert renamed.user_id == canonical.user_id
        assert renamed.roles == canonical.roles
        assert renamed.password_hash == StaticPasswordHasher().hash("admin")
        assert renamed.credential_version == canonical.credential_version + 1

    payload = state_store.load("users")
    assert payload is not None
    assert payload["seed_login_profile"] == NUMBERED_SEED_LOGIN_PROFILE

    teams = TeamRepository()
    seed_teams(teams, numbered)
    assert all(teams.get_profile(user.user_id) is not None for user in accounts)


def test_numbered_seed_credential_migration_runs_only_once() -> None:
    baseline = _users()
    state_store = MemoryStateStore()
    state_store.save(
        "users",
        {"users": [encode_value(user) for user in baseline.list_users()]},
    )
    settings = Settings(
        environment="local",
        local_numbered_seed_usernames=True,
        local_seed_credential="admin",
    )
    migrated = SeedUserRepository(settings, StaticPasswordHasher(), state_store)
    admin = migrated.get_by_username("admin1")
    assert admin is not None
    updated_hash = StaticPasswordHasher().hash("user-changed-password")
    changed = replace(
        admin,
        password_hash=updated_hash,
        credential_version=admin.credential_version + 1,
    )
    migrated.save(changed)

    restarted = SeedUserRepository(settings, StaticPasswordHasher(), state_store)

    restored = restarted.get_by_username("admin1")
    assert restored is not None
    assert restored.password_hash == changed.password_hash
    assert restored.credential_version == changed.credential_version


def test_disabling_numbered_profile_restores_canonical_names_without_duplicates() -> None:
    state_store = MemoryStateStore()
    numbered_settings = Settings(
        environment="local",
        local_numbered_seed_usernames=True,
        local_seed_credential="admin",
    )
    numbered = SeedUserRepository(numbered_settings, StaticPasswordHasher(), state_store)
    admin = numbered.get_by_username("admin1")
    assert admin is not None

    canonical = SeedUserRepository(
        Settings(environment="local"), StaticPasswordHasher(), state_store
    )

    restored = canonical.get_by_username("admin@example.test")
    assert restored is not None
    assert restored.user_id == admin.user_id
    assert restored.password_hash == admin.password_hash
    assert canonical.get_by_username("admin1") is None
    assert len(canonical.list_users()) == 53


def test_numbered_local_seed_identity_conflicts_fail_closed() -> None:
    baseline = _users()
    admin = baseline.get_by_username("admin@example.test")
    customer = baseline.get_by_username("user@example.test")
    assert admin is not None and customer is not None
    state_store = MemoryStateStore()
    state_store.save(
        "users",
        {
            "users": [
                encode_value(admin),
                encode_value(replace(customer, username="admin1")),
            ]
        },
    )

    settings = Settings(environment="local", local_numbered_seed_usernames=True)
    with pytest.raises(ValueError, match="Conflicting synthetic accounts"):
        SeedUserRepository(settings, StaticPasswordHasher(), state_store)


def test_seed_profile_reconciliation_updates_only_untouched_profiles() -> None:
    users = _users()
    teams = TeamRepository()
    seed_teams(teams, users)
    upgraded = users.get_by_username("analyst.2@example.test")
    edited = users.get_by_username("analyst.3@example.test")
    assert upgraded is not None and edited is not None

    legacy_title, legacy_specialisms, legacy_bio = LEGACY_PROFILE_SPECS[upgraded.username]
    teams.save_profile(
        UserProfile(
            user_id=upgraded.user_id,
            title=legacy_title,
            specialisms=legacy_specialisms,
            bio=legacy_bio,
        )
    )
    custom = UserProfile(
        user_id=edited.user_id,
        title="User-edited title",
        specialisms=("User-edited specialism",),
        bio="User-edited biography.",
    )
    teams.save_profile(custom)

    seed_teams(teams, users)

    reconciled = teams.get_profile(upgraded.user_id)
    assert reconciled is not None
    assert (reconciled.title, reconciled.specialisms, reconciled.bio) == PROFILE_SPECS[
        upgraded.username
    ]
    assert teams.get_profile(edited.user_id) == custom


def test_every_generic_analyst_is_seeded_into_an_operational_team() -> None:
    users = _users()
    teams = TeamRepository()
    seed_teams(teams, users)
    operational_teams = [
        team for team in teams.list_teams() if team.kind in {TeamKind.RFA, TeamKind.CM}
    ]
    member_ids = set().union(*(team_member_ids(team) for team in operational_teams))

    analysts = [user for user in users.list_users() if RoleName.INTELLIGENCE_ANALYST in user.roles]
    assert all(analyst.user_id in member_ids for analyst in analysts)
    memberships = {
        analyst.username: [
            team.kind for team in operational_teams if analyst.user_id in team_member_ids(team)
        ]
        for analyst in analysts
    }
    assert all(len(kinds) == 1 for kinds in memberships.values())
    assert sum(kinds == [TeamKind.RFA] for kinds in memberships.values()) == 14
    assert sum(kinds == [TeamKind.CM] for kinds in memberships.values()) == 10


def test_exact_legacy_route_seed_is_upgraded_but_edited_team_is_preserved() -> None:
    users = _users()
    teams = TeamRepository()

    def ids(*usernames: str):
        return tuple(
            user.user_id
            for username in usernames
            if (user := users.get_by_username(username)) is not None
        )

    legacy_rfa = OrgTeam(
        team_id=uuid4(),
        name="RFA Assessment Team",
        kind=TeamKind.RFA,
        capability_team_id="RFA-MARITIME",
        manager_user_ids=ids("rfa.manager@example.test"),
        member_user_ids=ids(
            "rfa.team@example.test",
            "analyst@example.test",
            "analyst.2@example.test",
            "analyst.3@example.test",
            "analyst.4@example.test",
        ),
    )
    edited_cm = OrgTeam(
        team_id=uuid4(),
        name="Collection Management Team",
        kind=TeamKind.CM,
        capability_team_id="CM-CYBER-SENSOR",
        manager_user_ids=ids("collection.manager@example.test"),
        member_user_ids=ids(
            "collection.team@example.test",
            "analyst@example.test",
            "analyst.3@example.test",
            "colleague@example.test",
        ),
    )
    teams.save_team(legacy_rfa)
    teams.save_team(edited_cm)

    seed_teams(teams, users)

    assert teams.get_team(legacy_rfa.team_id) == replace(
        legacy_rfa,
        member_user_ids=ids(
            "rfa.team@example.test",
            "analyst@example.test",
            "analyst.2@example.test",
            "analyst.4@example.test",
        ),
    )
    assert teams.get_team(edited_cm.team_id) == edited_cm


def test_existing_untouched_jioc_cell_adds_new_member_without_overwriting_edits() -> None:
    users = _users()
    manager = users.get_by_username("jioc.team@example.test")
    member = users.get_by_username("jioc.member@example.test")
    custom_member = users.get_by_username("user@example.test")
    assert manager is not None and member is not None and custom_member is not None

    teams = TeamRepository()
    old_cell = OrgTeam(
        team_id=uuid4(),
        name="JIOC Routing Cell",
        kind=TeamKind.JIOC,
        member_user_ids=(manager.user_id,),
    )
    teams.save_team(old_cell)
    seed_teams(teams, users)
    assert teams.get_team(old_cell.team_id) == replace(
        old_cell,
        manager_user_ids=(manager.user_id,),
        member_user_ids=(member.user_id,),
    )

    edited_teams = TeamRepository()
    edited_cell = replace(
        old_cell,
        manager_user_ids=(manager.user_id,),
        member_user_ids=(custom_member.user_id,),
    )
    edited_teams.save_team(edited_cell)
    seed_teams(edited_teams, users)
    assert edited_teams.get_team(old_cell.team_id) == edited_cell
