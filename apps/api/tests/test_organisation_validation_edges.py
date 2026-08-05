from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.organisation import (
    DeliveryRoute,
    EffectiveAuthorityEpoch,
    FindingSeverity,
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
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

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


def _unit() -> OrganisationUnit:
    return OrganisationUnit(
        uuid4(), "Synthetic Unit", "Unit", OrganisationCategory.COMMAND, None, NOW
    )


def _membership() -> TeamMembership:
    return TeamMembership(
        uuid4(),
        uuid4(),
        uuid4(),
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        uuid4(),
        "Synthetic reason",
        "test",
    )


def _grant() -> OrganisationManagementGrant:
    return OrganisationManagementGrant(
        uuid4(),
        uuid4(),
        uuid4(),
        ManagementAction.TASK_VIEW,
        False,
        NOW,
        uuid4(),
        "Synthetic grant",
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"version": 0}, "version must be positive"),
        ({"name": ""}, "trimmed characters"),
        ({"name": " bad"}, "trimmed characters"),
        ({"name": "bad\nname"}, "control characters"),
        ({"valid_until": NOW}, "later than valid_from"),
    ],
)
def test_unit_validation_edges(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(_unit(), **changes)


def test_topology_and_membership_validation_edges() -> None:
    unit = _unit()
    revision = OrganisationTopologyRevision(
        uuid4(), unit.unit_id, None, (unit.unit_id,), NOW, uuid4(), uuid4()
    )
    with pytest.raises(ValueError, match="end with its unit"):
        replace(revision, path=())
    membership = _membership()
    with pytest.raises(ValueError, match="requires valid_until"):
        replace(membership, state=MembershipState.ENDED, assignment_eligible=False)
    with pytest.raises(ValueError, match="version must be positive"):
        replace(membership, version=0)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"delegation_depth": 3}, "between zero and two"),
        ({"source_grant_id": None, "delegation_depth": 1}, "requires its source"),
        ({"version": 0}, "version must be positive"),
        ({"revoked_at": NOW - timedelta(seconds=1)}, "cannot precede"),
        (
            {"valid_until": NOW + timedelta(days=1), "revoked_at": NOW + timedelta(days=2)},
            "cannot follow",
        ),
    ],
)
def test_grant_validation_edges(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(_grant(), **changes)
    grant = _grant()
    with pytest.raises(ValueError, match="delegate from itself"):
        replace(grant, source_grant_id=grant.grant_id)


def test_delivery_capability_and_epoch_validation_edges() -> None:
    profile = TeamDeliveryProfile(uuid4(), uuid4(), DeliveryRoute.RFA, 5, 37.5)
    with pytest.raises(ValueError, match="weekly_hours"):
        replace(profile, weekly_hours=0)
    with pytest.raises(ValueError, match="policy_version"):
        replace(profile, policy_version=0)
    coverage = TeamCapabilityCoverage(uuid4(), profile.profile_id, "imagery", 3, NOW, uuid4())
    with pytest.raises(ValueError, match="proficiency"):
        replace(coverage, proficiency=0)
    with pytest.raises(ValueError, match="policy_version"):
        replace(coverage, policy_version=0)
    with pytest.raises(ValueError, match="authority epoch"):
        EffectiveAuthorityEpoch(uuid4(), uuid4(), 0, NOW)


def test_reconciliation_temporal_validation_edges() -> None:
    running = OrganisationReconciliationCheckpoint(
        uuid4(), "teams", "a" * 64, ReconciliationStatus.RUNNING, NOW, {}
    )
    with pytest.raises(ValueError, match="running checkpoint"):
        replace(running, completed_at=NOW)
    with pytest.raises(ValueError, match="terminal checkpoint"):
        replace(running, status=ReconciliationStatus.COMPLETED)
    completed = replace(running, status=ReconciliationStatus.COMPLETED, completed_at=NOW)
    with pytest.raises(ValueError, match="cannot precede"):
        replace(completed, completed_at=NOW - timedelta(seconds=1))
    finding = OrganisationReconciliationFinding(
        uuid4(),
        completed.checkpoint_id,
        "synthetic",
        FindingSeverity.BLOCKING,
        "user",
        {},
        NOW,
    )
    with pytest.raises(ValueError, match="resolved_at cannot precede"):
        replace(finding, resolved_at=NOW - timedelta(seconds=1))


def test_atomic_reconciliation_plan_validation_edges() -> None:
    checkpoint = OrganisationReconciliationCheckpoint(
        uuid4(), "teams", "a" * 64, ReconciliationStatus.COMPLETED, NOW, {}, NOW
    )
    plan = OrganisationReconciliationPlan(checkpoint, uuid4(), NOW, (), (), (), (), ())
    assert plan.checkpoint == checkpoint
    with pytest.raises(ValueError, match="completed checkpoint"):
        OrganisationReconciliationPlan(
            replace(checkpoint, status=ReconciliationStatus.RUNNING, completed_at=None),
            uuid4(),
            NOW,
            (),
            (),
            (),
            (),
            (),
        )
    with pytest.raises(ValueError, match="completion must match"):
        replace(plan, effective_at=NOW + timedelta(seconds=1))
    unit = _unit()
    other = _unit()
    revision = OrganisationTopologyRevision(
        uuid4(), other.unit_id, None, (other.unit_id,), NOW, uuid4(), uuid4()
    )
    with pytest.raises(ValueError, match="identities must match"):
        replace(plan, units=((unit, revision),))
