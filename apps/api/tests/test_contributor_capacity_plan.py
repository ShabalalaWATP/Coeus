"""Contributor capacity-plan validation and evidence tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.work_package_contributors import (
    ContributorCapacityPlan,
    ContributorChangeRequest,
    ContributorOperation,
    contributor_change_hash,
)


def _plan() -> ContributorCapacityPlan:
    start = datetime(2026, 8, 5, 9, tzinfo=UTC)
    return ContributorCapacityPlan(uuid4(), start, start + timedelta(hours=1), 60, "capacity")


def _request(plan: ContributorCapacityPlan | None = None) -> ContributorChangeRequest:
    return ContributorChangeRequest(
        uuid4(),
        uuid4(),
        uuid4(),
        ContributorOperation.ADD,
        1,
        1,
        uuid4(),
        1,
        uuid4(),
        1,
        0,
        "a" * 64,
        plan,
    )


def test_capacity_plan_is_included_in_actor_bound_evidence() -> None:
    actor = uuid4()
    plain = _request()
    planned = replace(plain, capacity_plan=_plan())
    assert contributor_change_hash(actor, plain) != contributor_change_hash(actor, planned)
    assert contributor_change_hash(actor, planned) != contributor_change_hash(uuid4(), planned)


@pytest.mark.parametrize(("minutes", "key"), [(0, "key"), (10, "key"), (15, "")])
def test_capacity_plan_rejects_invalid_effort_or_identity(minutes: int, key: str) -> None:
    plan = _plan()
    with pytest.raises(ValueError):
        replace(plan, reserved_minutes=minutes, idempotency_key=key)


def test_capacity_plan_requires_valid_aware_bounds() -> None:
    plan = _plan()
    with pytest.raises(ValueError):
        replace(plan, starts_at=plan.ends_at)
    with pytest.raises(ValueError):
        replace(plan, starts_at=plan.starts_at.replace(tzinfo=None))


def test_ending_contributor_cannot_create_capacity() -> None:
    with pytest.raises(ValueError):
        replace(_request(_plan()), operation=ContributorOperation.END)
