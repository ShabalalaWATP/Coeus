"""Evidence for realistic, deterministic and authorised synthetic work."""

from coeus.core.config import Settings
from coeus.domain.teams import UserProfile
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.synthetic_capacity_manifest import (
    synthetic_capacity_reservations,
    synthetic_workload_scenarios,
)
from coeus.repositories.synthetic_organisation_integrity import (
    inspect_synthetic_organisation_manifest,
)
from coeus.repositories.synthetic_organisation_manifest import synthetic_posting_specs
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs
from coeus.repositories.teams import TeamRepository
from coeus.repositories.teams_seed import seed_teams
from coeus.repositories.teams_seed_profiles import LEGACY_PROFILE_SPECS, PROFILE_SPECS


class _Hasher:
    def hash(self, credential: str) -> str:
        return f"hash:{credential}"

    def verify(self, stored_hash: str, credential: str) -> bool:
        return stored_hash == self.hash(credential)

    def needs_rehash(self, stored_hash: str) -> bool:
        return False


def _users() -> SeedUserRepository:
    return SeedUserRepository(Settings(environment="test"), _Hasher())


def test_analyst_personas_clearance_and_access_are_varied_but_authorised() -> None:
    users = _users()
    access = SeedAccessRepository(users)
    analysts = tuple(user for user in users.list_users() if user.username.startswith("analyst"))
    profiles = tuple(PROFILE_SPECS[user.username] for user in analysts)
    assert len(analysts) == 24
    assert len({item[1] for item in profiles}) == 24
    assert len({user.clearance_level for user in analysts}) == 2
    assert users.get_by_username("analyst.24@example.test").is_active is False  # type: ignore[union-attr]
    assert all(access.active_acg_ids_for_user(user.user_id) for user in analysts)
    assert len({access.active_acg_ids_for_user(user.user_id) for user in analysts}) >= 7


def test_previous_generic_analyst_profile_upgrades_without_overwriting_edits() -> None:
    users = _users()
    teams = TeamRepository()
    seed_teams(teams, users)
    account = users.get_by_username("analyst.5@example.test")
    assert account is not None
    title, specialisms, bio = LEGACY_PROFILE_SPECS[account.username]
    teams.save_profile(UserProfile(account.user_id, title, specialisms, bio))
    seed_teams(teams, users)
    upgraded = teams.get_profile(account.user_id)
    assert upgraded is not None
    assert (upgraded.title, upgraded.specialisms, upgraded.bio) == PROFILE_SPECS[account.username]


def test_task_distribution_is_stable_capacity_aware_and_single_home() -> None:
    first = synthetic_task_specs()
    assert first == synthetic_task_specs()
    active_home = {
        item.username: item.unit_key
        for item in synthetic_posting_specs()
        if item.assignment_eligible and item.state.value == "active"
    }
    assert all(
        task.assignee_username is None or active_home[task.assignee_username] == task.unit_key
        for task in first
    )
    assert "__capacity_allocate__" not in {item.assignee_username for item in first}


def test_workload_and_transfer_manifest_has_machine_readable_evidence() -> None:
    report = inspect_synthetic_organisation_manifest()
    assert report.valid, report.errors
    assert report.posting_count == 54
    assert report.transfer_evidence_count == 2
    assert report.capacity_reservation_count == 2
    assert {item.state for item in synthetic_workload_scenarios()} == {
        "idle",
        "loaded",
        "overloaded",
        "unavailable",
    }
    assert all(
        0 < item.minutes <= 480 and item.minutes % 15 == 0
        for item in synthetic_capacity_reservations()
    )
