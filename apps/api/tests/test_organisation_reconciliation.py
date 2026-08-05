from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.organisation import (
    OrganisationReconciliationCheckpoint,
    OrganisationReconciliationFinding,
    OrganisationTopologyRevision,
    OrganisationUnit,
    ReconciliationStatus,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)
from coeus.domain.organisation_reconciliation import OrganisationReconciliationPlan
from coeus.domain.teams import OrgTeam, TeamKind
from coeus.services.organisation_reconciliation import (
    OrganisationReconciliationService,
    _source_digest,
)

NOW = datetime(2026, 8, 3, 10, tzinfo=UTC)


class RecordingOrganisationRepository:
    def __init__(self) -> None:
        self.units: dict[UUID, OrganisationUnit] = {}
        self.memberships: dict[UUID, TeamMembership] = {}
        self.profiles: dict[UUID, TeamDeliveryProfile] = {}
        self.coverage: dict[UUID, TeamCapabilityCoverage] = {}
        self.checkpoints: dict[UUID, OrganisationReconciliationCheckpoint] = {}
        self.findings: dict[UUID, OrganisationReconciliationFinding] = {}

    def apply_reconciliation(self, plan: OrganisationReconciliationPlan) -> None:
        for unit, revision in plan.units:
            self.upsert_unit(unit, revision)
        for profile in plan.delivery_profiles:
            self.upsert_delivery_profile(profile)
        for coverage in plan.capability_coverage:
            self.upsert_capability_coverage(coverage)
        for membership in plan.memberships:
            self.upsert_membership(membership)
        self.upsert_checkpoint(plan.checkpoint)
        for finding in plan.findings:
            self.upsert_finding(finding)

    def get_unit(self, unit_id: UUID) -> OrganisationUnit | None:
        return self.units.get(unit_id)

    def list_roots(self, *, limit: int = 100) -> tuple[OrganisationUnit, ...]:
        return tuple(self.units.values())[:limit]

    def list_children(self, unit_id: UUID, *, limit: int = 100) -> tuple[OrganisationUnit, ...]:
        return ()

    def list_ancestors(
        self, unit_id: UUID, *, maximum_depth: int = 12
    ) -> tuple[OrganisationUnit, ...]:
        return ()

    def list_descendants(
        self, unit_id: UUID, *, maximum_depth: int = 12, limit: int = 1_000
    ) -> tuple[OrganisationUnit, ...]:
        return ()

    def list_memberships(self, user_id: UUID) -> tuple[TeamMembership, ...]:
        return tuple(item for item in self.memberships.values() if item.user_id == user_id)

    def effective_membership(self, user_id: UUID, effective_at: datetime) -> TeamMembership | None:
        return next(iter(self.list_memberships(user_id)), None)

    def effective_grants(self, manager_user_id: UUID, effective_at: datetime) -> tuple[object, ...]:
        return ()

    def upsert_unit(self, unit: OrganisationUnit, revision: OrganisationTopologyRevision) -> None:
        assert revision.path == (unit.unit_id,)
        self.units[unit.unit_id] = unit

    def upsert_membership(self, membership: TeamMembership) -> None:
        self.memberships[membership.membership_id] = membership

    def upsert_management_grant(self, grant: object) -> None:
        raise AssertionError("not expected")

    def upsert_delivery_profile(self, profile: TeamDeliveryProfile) -> None:
        self.profiles[profile.profile_id] = profile

    def upsert_capability_coverage(self, coverage: TeamCapabilityCoverage) -> None:
        self.coverage[coverage.coverage_id] = coverage

    def upsert_authority_epoch(self, epoch: object) -> None:
        raise AssertionError("not expected")

    def upsert_checkpoint(self, checkpoint: OrganisationReconciliationCheckpoint) -> None:
        self.checkpoints[checkpoint.checkpoint_id] = checkpoint

    def upsert_finding(self, finding: OrganisationReconciliationFinding) -> None:
        self.findings[finding.finding_id] = finding


def _user(*, active: bool = True, analyst: bool = True) -> UserAccount:
    roles = frozenset({RoleName.INTELLIGENCE_ANALYST}) if analyst else frozenset({RoleName.USER})
    return UserAccount(uuid4(), "user@example.test", "User", roles, frozenset(), "hash", active, 1)


def _team(*, member_ids: tuple[UUID, ...] = (), manager_ids: tuple[UUID, ...] = ()) -> OrgTeam:
    return OrgTeam(
        team_id=uuid4(),
        name="RFA Assessment Team",
        kind=TeamKind.RFA,
        manager_user_ids=manager_ids,
        member_user_ids=member_ids,
        capability_team_id="RFA-MARITIME",
        created_at=NOW,
    )


def test_reconciliation_preserves_team_id_and_is_idempotent() -> None:
    repository = RecordingOrganisationRepository()
    analyst = _user()
    team = _team(member_ids=(analyst.user_id,))
    service = OrganisationReconciliationService(repository)

    first = service.reconcile(
        teams=(team,), users=(analyst,), actor_user_id=uuid4(), effective_at=NOW
    )
    second = service.reconcile(
        teams=(team,), users=(analyst,), actor_user_id=uuid4(), effective_at=NOW
    )

    assert first == second
    assert set(repository.units) == {team.team_id}
    assert len(repository.memberships) == 1
    assert next(iter(repository.memberships.values())).assignment_eligible is True
    assert len(repository.profiles) == 1
    assert len(repository.coverage) == 1
    assert next(iter(repository.checkpoints.values())).status is ReconciliationStatus.COMPLETED


def test_overlapping_legacy_membership_is_quarantined_without_membership() -> None:
    repository = RecordingOrganisationRepository()
    analyst = _user()
    first_team = _team(member_ids=(analyst.user_id,))
    second_team = _team(member_ids=(analyst.user_id,))

    result = OrganisationReconciliationService(repository).reconcile(
        teams=(first_team, second_team),
        users=(analyst,),
        actor_user_id=uuid4(),
        effective_at=NOW,
    )

    assert result.blocking_findings == 1
    assert not repository.memberships
    finding = next(iter(repository.findings.values()))
    assert finding.finding_code == "overlapping_legacy_membership"
    assert finding.details["team_ids"] == sorted(
        (str(first_team.team_id), str(second_team.team_id))
    )


def test_manager_precedence_and_inactive_people_are_not_assignable() -> None:
    repository = RecordingOrganisationRepository()
    manager = _user()
    inactive = _user(active=False)
    team = _team(
        member_ids=(manager.user_id, inactive.user_id),
        manager_ids=(manager.user_id,),
    )

    OrganisationReconciliationService(repository).reconcile(
        teams=(team,),
        users=(manager, inactive),
        actor_user_id=uuid4(),
        effective_at=NOW,
    )

    by_user = {item.user_id: item for item in repository.memberships.values()}
    assert by_user[manager.user_id].role.value == "manager"
    assert by_user[manager.user_id].assignment_eligible is False
    assert by_user[inactive.user_id].state.value == "suspended"
    assert by_user[inactive.user_id].assignment_eligible is False


def test_missing_legacy_user_is_a_blocking_finding() -> None:
    repository = RecordingOrganisationRepository()
    missing_user_id = uuid4()
    team = _team(member_ids=(missing_user_id,))

    result = OrganisationReconciliationService(repository).reconcile(
        teams=(team,), users=(), actor_user_id=uuid4(), effective_at=NOW
    )

    assert result.memberships_written == 0
    assert result.blocking_findings == 1
    assert next(iter(repository.findings.values())).finding_code == "legacy_member_not_found"


def test_inactive_team_cannot_create_assignment_eligible_membership() -> None:
    repository = RecordingOrganisationRepository()
    analyst = _user()
    team = _team(member_ids=(analyst.user_id,))
    team = OrgTeam(**{**vars(team), "is_active": False})

    OrganisationReconciliationService(repository).reconcile(
        teams=(team,), users=(analyst,), actor_user_id=uuid4(), effective_at=NOW
    )

    membership = next(iter(repository.memberships.values()))
    assert membership.state.value == "suspended"
    assert membership.assignment_eligible is False


def test_user_authority_changes_produce_a_new_source_digest() -> None:
    repository = RecordingOrganisationRepository()
    analyst = _user()
    team = _team(member_ids=(analyst.user_id,))
    service = OrganisationReconciliationService(repository)

    active = service.reconcile(
        teams=(team,), users=(analyst,), actor_user_id=uuid4(), effective_at=NOW
    )
    inactive = service.reconcile(
        teams=(team,),
        users=(UserAccount(**{**vars(analyst), "is_active": False}),),
        actor_user_id=uuid4(),
        effective_at=NOW,
    )

    assert active.source_digest != inactive.source_digest


def test_unreferenced_user_changes_do_not_churn_the_source_digest() -> None:
    analyst = _user()
    unrelated = UserAccount(
        uuid4(),
        "customer@example.test",
        "Synthetic Customer",
        frozenset({RoleName.USER}),
        frozenset(),
        "hash",
        True,
        1,
    )
    team = _team(member_ids=(analyst.user_id,))
    changed = UserAccount(**{**vars(unrelated), "is_active": False})

    assert _source_digest((team,), (analyst, unrelated)) == _source_digest(
        (team,), (analyst, changed)
    )
