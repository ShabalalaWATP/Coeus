from dataclasses import replace

from coeus.core.config import Settings
from coeus.domain.auth import RoleName
from coeus.domain.teams import TeamKind, UserProfile, team_member_ids
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import MemoryStateStore
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.auth_seed import seed_user_specs
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

    assert len(accounts) == 15
    assert len({user.display_name for user in accounts}) == 15
    assert {user.username for user in analysts} == {
        "analyst@example.test",
        "analyst.2@example.test",
        "analyst.3@example.test",
        "analyst.4@example.test",
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

    assert len(restored.list_users()) == 15
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
