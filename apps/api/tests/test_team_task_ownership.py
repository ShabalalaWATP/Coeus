from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.team_task_ownership import (
    TeamTaskOwnership,
    TeamTaskOwnershipState,
    WorkflowLeg,
)

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


def _ownership() -> TeamTaskOwnership:
    return TeamTaskOwnership(
        ownership_id=uuid4(),
        ticket_id=uuid4(),
        workflow_leg=WorkflowLeg.RFA,
        owning_unit_id=uuid4(),
        manager_user_id=None,
        state=TeamTaskOwnershipState.TRIAGE,
        topology_revision_id=uuid4(),
        capability_policy_version=1,
        version=1,
        history_reference=uuid4(),
        provenance="synthetic-test",
        created_at=NOW,
        target_date=date(2026, 8, 10),
    )


def test_ownership_requires_bounded_versions_and_acceptance_time() -> None:
    ownership = _ownership()
    with pytest.raises(ValueError, match="capability_policy_version"):
        replace(ownership, capability_policy_version=0)
    with pytest.raises(ValueError, match="version must be positive"):
        replace(ownership, version=0)
    with pytest.raises(ValueError, match="require accepted_at"):
        replace(ownership, state=TeamTaskOwnershipState.ACTIVE)
    with pytest.raises(ValueError, match="require accepted_at"):
        replace(ownership, accepted_at=NOW)
    with pytest.raises(ValueError, match="cannot precede"):
        replace(
            ownership,
            state=TeamTaskOwnershipState.ACCEPTED,
            accepted_at=NOW - timedelta(seconds=1),
        )


def test_accepted_ownership_is_valid() -> None:
    ownership = replace(
        _ownership(),
        state=TeamTaskOwnershipState.ACCEPTED,
        accepted_at=NOW + timedelta(minutes=1),
    )
    assert ownership.accepted_at is not None
