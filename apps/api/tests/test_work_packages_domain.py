from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_packages import (
    CanonicalWorkPackage,
    CanonicalWorkPackageState,
    CapacityReservation,
    CapacityReservationConflict,
    CapacityReservationState,
    CapacityUnavailable,
    CapacityUnknown,
    ReserveCapacityCommand,
    completion_is_allowed,
    validate_dependency_graph,
)

NOW = datetime(2026, 8, 3, tzinfo=UTC)


def _package(**changes: Any) -> CanonicalWorkPackage:
    package = CanonicalWorkPackage(
        uuid4(),
        uuid4(),
        WorkflowLeg.RFA,
        uuid4(),
        uuid4(),
        "Assess synthetic reporting",
        CanonicalWorkPackageState.READY,
        1,
        1,
        "test",
        NOW,
        NOW,
        estimated_minutes=120,
        remaining_minutes=120,
    )
    return replace(package, **changes)


def test_dependency_graph_and_completion_require_completed_predecessors() -> None:
    first = _package(state=CanonicalWorkPackageState.COMPLETE, remaining_minutes=0)
    second = _package(
        ticket_id=first.ticket_id,
        predecessor_package_ids=(first.package_id,),
        sort_order=2,
    )
    validate_dependency_graph((first, second))
    assert completion_is_allowed(second, (first, second))
    pending_first = replace(first, state=CanonicalWorkPackageState.READY)
    assert not completion_is_allowed(second, (pending_first, second))


@pytest.mark.parametrize(
    "packages,error",
    [
        (lambda a, _b: (a, a), "identities"),
        (lambda a, b: (a, replace(b, predecessor_package_ids=(uuid4(),))), "same task"),
        (
            lambda a, b: (
                a,
                replace(b, ticket_id=uuid4(), predecessor_package_ids=(a.package_id,)),
            ),
            "cross a ticket",
        ),
        (
            lambda a, b: (
                replace(a, predecessor_package_ids=(b.package_id,)),
                replace(b, predecessor_package_ids=(a.package_id,)),
            ),
            "acyclic",
        ),
    ],
)
def test_dependency_graph_rejects_invalid_edges(packages: object, error: str) -> None:
    first = _package()
    second = _package(ticket_id=first.ticket_id, sort_order=2)
    with pytest.raises(ValueError, match=error):
        validate_dependency_graph(packages(first, second))  # type: ignore[operator]


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"title": "x"}, "title"),
        ({"sort_order": -1}, "order"),
        ({"estimated_minutes": None, "remaining_minutes": 1}, "requires an estimate"),
        ({"estimated_minutes": 16, "remaining_minutes": 15}, "estimated effort"),
        ({"remaining_minutes": 121}, "remaining effort"),
        ({"priority": 6}, "priority"),
        ({"priority_override_reason": "x" * 501}, "reason"),
        ({"accountable_user_id": None}, "accountable"),
    ],
)
def test_work_package_validation(changes: dict[str, object], error: str) -> None:
    with pytest.raises(ValueError, match=error):
        _package(**changes)


def test_owner_contributor_and_blocked_evidence_validation() -> None:
    owner = uuid4()
    with pytest.raises(ValueError, match="also be a contributor"):
        _package(accountable_user_id=owner, contributor_user_ids=(owner,))
    contributor = uuid4()
    with pytest.raises(ValueError, match="unique"):
        _package(contributor_user_ids=(contributor, contributor))
    with pytest.raises(ValueError, match="structured reason"):
        _package(state=CanonicalWorkPackageState.BLOCKED)
    blocked = _package(
        state=CanonicalWorkPackageState.BLOCKED,
        blocked_code="SOURCE_DELAY",
        blocked_note="Awaiting a synthetic source.",
        review_at=NOW + timedelta(days=1),
    )
    assert blocked.blocked_code == "SOURCE_DELAY"
    with pytest.raises(ValueError, match="only valid"):
        replace(blocked, state=CanonicalWorkPackageState.READY)


def test_capacity_reservation_validation() -> None:
    values: dict[str, Any] = dict(
        reservation_id=uuid4(),
        user_id=uuid4(),
        ticket_id=uuid4(),
        workflow_leg=WorkflowLeg.RFA,
        package_id=uuid4(),
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=2),
        reserved_minutes=120,
        state=CapacityReservationState.ACTIVE,
        idempotency_key="capacity-test",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    assert CapacityReservation(**values).reserved_minutes == 120
    for changes, message in (
        ({"ends_at": NOW}, "end"),
        ({"reserved_minutes": 17}, "15-minute"),
        ({"idempotency_key": ""}, "identity"),
        ({"expires_at": NOW}, "expiry"),
    ):
        with pytest.raises(ValueError, match=message):
            CapacityReservation(**(values | changes))


def test_reserve_capacity_command_and_errors() -> None:
    values: dict[str, Any] = dict(
        reservation_id=uuid4(),
        actor_user_id=uuid4(),
        user_id=uuid4(),
        ticket_id=uuid4(),
        workflow_leg=WorkflowLeg.RFA,
        package_id=uuid4(),
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=2),
        reserved_minutes=60,
        idempotency_key="reserve-command",
        expected_package_version=1,
    )
    assert ReserveCapacityCommand(**values).reserved_minutes == 60
    for changes, message in (
        ({"starts_at": NOW.replace(tzinfo=None)}, "timezone"),
        ({"ends_at": NOW}, "end"),
        ({"reserved_minutes": 1}, "15-minute"),
        ({"idempotency_key": ""}, "idempotency"),
        ({"expected_package_version": 0}, "version"),
    ):
        with pytest.raises(ValueError, match=message):
            ReserveCapacityCommand(**(values | changes))
    assert issubclass(CapacityReservationConflict, ValueError)
    assert issubclass(CapacityUnavailable, ValueError)
    assert issubclass(CapacityUnknown, ValueError)
