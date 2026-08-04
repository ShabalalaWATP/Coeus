"""Validation and schema-contract tests for the inactive organisation foundation."""

import importlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.organisation import (
    DeliveryRoute,
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationClosureRow,
    OrganisationManagementGrant,
    OrganisationTopologyRevision,
    OrganisationUnit,
    TeamDeliveryProfile,
    TeamMembership,
    validate_membership_history,
)
from coeus.persistence.organisation_schema import organisation_schema_statements

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


def _unit() -> OrganisationUnit:
    return OrganisationUnit(
        uuid4(), "Defence Intelligence", "DI", OrganisationCategory.COMMAND, None, NOW
    )


def _membership(
    user_id: object, start: datetime, end: datetime | None, *, state: MembershipState
) -> TeamMembership:
    return TeamMembership(
        uuid4(),
        user_id,  # type: ignore[arg-type]
        uuid4(),
        MembershipRole.MEMBER,
        state,
        state is MembershipState.ACTIVE,
        start,
        uuid4(),
        "Synthetic fixture",
        "test",
        end,
    )


def test_unit_and_closure_validate_tree_invariants() -> None:
    unit = _unit()
    with pytest.raises(ValueError, match="parent itself"):
        replace(unit, parent_unit_id=unit.unit_id)
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(unit, valid_from=datetime(2026, 8, 3))
    with pytest.raises(ValueError, match="depth-zero"):
        OrganisationClosureRow(unit.unit_id, uuid4(), 0)
    with pytest.raises(ValueError, match="between 0 and 12"):
        OrganisationClosureRow(unit.unit_id, uuid4(), 13)
    assert OrganisationClosureRow(unit.unit_id, unit.unit_id, 0).depth == 0


def test_topology_revision_requires_an_acyclic_bounded_matching_path() -> None:
    root, child = uuid4(), uuid4()
    revision = OrganisationTopologyRevision(
        uuid4(), child, root, (root, child), NOW, uuid4(), uuid4()
    )
    assert revision.path == (root, child)
    with pytest.raises(ValueError, match="parent"):
        replace(revision, parent_unit_id=uuid4())
    with pytest.raises(ValueError, match="cycle"):
        replace(revision, path=(root, root, child))
    with pytest.raises(ValueError, match="maximum depth"):
        replace(revision, path=(*tuple(uuid4() for _ in range(13)), child), parent_unit_id=None)


def test_half_open_membership_history_allows_adjacent_but_rejects_overlap() -> None:
    user_id = uuid4()
    boundary = NOW + timedelta(days=30)
    old = _membership(user_id, NOW, boundary, state=MembershipState.ENDED)
    current = _membership(user_id, boundary, None, state=MembershipState.ACTIVE)
    validate_membership_history((old, current))
    with pytest.raises(ValueError, match="cannot overlap"):
        validate_membership_history(
            (old, replace(current, valid_from=boundary - timedelta(seconds=1)))
        )
    cancelled = replace(
        current,
        membership_id=uuid4(),
        state=MembershipState.CANCELLED,
        assignment_eligible=False,
        valid_from=NOW,
    )
    validate_membership_history((old, current, cancelled))


def test_membership_grant_and_delivery_profile_reject_unsafe_values() -> None:
    membership = _membership(uuid4(), NOW, None, state=MembershipState.ACTIVE)
    with pytest.raises(ValueError, match="only an active"):
        replace(membership, state=MembershipState.SUSPENDED)
    grant = OrganisationManagementGrant(
        uuid4(),
        uuid4(),
        uuid4(),
        ManagementAction.TASK_ASSIGN,
        True,
        NOW,
        uuid4(),
        "Temporary synthetic management cover",
    )
    with pytest.raises(ValueError, match="source grant"):
        replace(grant, delegation_depth=1)
    profile = TeamDeliveryProfile(uuid4(), uuid4(), DeliveryRoute.RFA, 5, 37.5)
    with pytest.raises(ValueError, match="wip_limit"):
        replace(profile, wip_limit=0)


def test_migration_uses_exact_runtime_schema_and_expected_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(
        "coeus.db.migrations.versions.20260803_0017_organisation_foundation"
    )
    executed: list[str] = []
    monkeypatch.setattr(module.op, "execute", executed.append)
    module.upgrade()
    assert module.revision == "20260803_0017"
    assert module.down_revision == "20260801_0016"
    assert tuple(executed) == tuple(organisation_schema_statements())


def test_schema_declares_postgres_integrity_and_external_user_identifiers() -> None:
    ddl = "\n".join(organisation_schema_statements()).lower()
    assert "create extension if not exists btree_gist" in ddl
    assert "depth between 0 and 12" in ddl
    assert "ck_organisation_unit_not_self_parent" in ddl
    assert "ex_team_memberships_non_overlapping" in ddl
    assert "tstzrange(valid_from, valid_until, '[)')" in ddl
    assert "where (state <> 'cancelled')" in ddl
    assert "unit_id uuid not null unique" in ddl
    assert "references users" not in ddl
