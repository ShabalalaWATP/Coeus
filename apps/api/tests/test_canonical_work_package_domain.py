"""Invariants a canonical work package and its reservation must satisfy."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_packages import (
    CanonicalWorkPackage,
    CanonicalWorkPackageState,
    ReserveCapacityCommand,
)

NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)
PACKAGE, OWNER = uuid4(), uuid4()


def _package(**overrides: object) -> CanonicalWorkPackage:
    values: dict[str, object] = {
        "package_id": PACKAGE,
        "ticket_id": uuid4(),
        "workflow_leg": WorkflowLeg.RFA,
        "owning_unit_id": uuid4(),
        "accountable_user_id": OWNER,
        "title": "Assess regional shipping",
        "state": CanonicalWorkPackageState.IN_PROGRESS,
        "sort_order": 0,
        "version": 1,
        "provenance": "test",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return CanonicalWorkPackage(**values)  # type: ignore[arg-type]


def test_a_well_formed_package_is_accepted() -> None:
    assert _package().title == "Assess regional shipping"


@pytest.mark.parametrize("title", ["ab", " ab ", "x" * 181])
def test_a_title_is_bounded_after_trimming(title: str) -> None:
    with pytest.raises(ValueError, match="3 to 180 characters"):
        _package(title=title)


@pytest.mark.parametrize("overrides", [{"sort_order": -1}, {"version": 0}])
def test_order_and_version_must_be_positive(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="order and version must be positive"):
        _package(**overrides)


@pytest.mark.parametrize(
    "state",
    [CanonicalWorkPackageState.PENDING, CanonicalWorkPackageState.CANCELLED],
)
def test_only_a_pending_or_cancelled_package_may_have_no_owner(
    state: CanonicalWorkPackageState,
) -> None:
    assert _package(state=state, accountable_user_id=None).accountable_user_id is None
    with pytest.raises(ValueError, match="requires one accountable owner"):
        _package(state=CanonicalWorkPackageState.READY, accountable_user_id=None)


def test_the_owner_cannot_also_be_listed_as_a_contributor() -> None:
    with pytest.raises(ValueError, match="cannot also be a contributor"):
        _package(contributor_user_ids=(OWNER,))


def test_contributors_are_listed_once_each() -> None:
    contributor = uuid4()
    assert _package(contributor_user_ids=(contributor,)).contributor_user_ids == (contributor,)
    with pytest.raises(ValueError, match="contributors must be unique"):
        _package(contributor_user_ids=(contributor, contributor))


def test_a_package_cannot_be_its_own_predecessor() -> None:
    assert _package(predecessor_package_ids=(uuid4(),)).predecessor_package_ids
    with pytest.raises(ValueError, match="cannot depend on itself"):
        _package(predecessor_package_ids=(PACKAGE,))


def test_remaining_effort_needs_an_estimate_to_measure_against() -> None:
    assert _package(estimated_minutes=120, remaining_minutes=60).remaining_minutes == 60
    assert _package(estimated_minutes=None, remaining_minutes=None).remaining_minutes is None
    with pytest.raises(ValueError, match="remaining effort requires an estimate"):
        _package(estimated_minutes=None, remaining_minutes=60)


def test_blocking_evidence_belongs_only_to_a_blocked_package() -> None:
    blocked = _package(
        state=CanonicalWorkPackageState.BLOCKED,
        blocked_code="awaiting_source",
        blocked_note="Waiting on imagery.",
        review_at=NOW + timedelta(days=1),
    )
    assert blocked.blocked_code == "awaiting_source"

    with pytest.raises(ValueError, match="only valid while work is blocked"):
        _package(blocked_note="Waiting on imagery.")
    with pytest.raises(ValueError, match="blocked note is too long"):
        _package(
            state=CanonicalWorkPackageState.BLOCKED,
            blocked_code="awaiting_source",
            blocked_note="x" * 1001,
            review_at=NOW + timedelta(days=1),
        )


def _reservation(**overrides: object) -> ReserveCapacityCommand:
    values: dict[str, object] = {
        "reservation_id": uuid4(),
        "actor_user_id": uuid4(),
        "user_id": OWNER,
        "ticket_id": uuid4(),
        "workflow_leg": WorkflowLeg.RFA,
        "package_id": PACKAGE,
        "starts_at": NOW,
        "ends_at": NOW + timedelta(hours=2),
        "reserved_minutes": 120,
        "idempotency_key": "reservation-1",
        "expected_package_version": 1,
    }
    values.update(overrides)
    return ReserveCapacityCommand(**values)  # type: ignore[arg-type]


def test_a_reservation_names_a_known_participant_role_and_a_current_version() -> None:
    assert _reservation().participant_role == "accountable"
    assert _reservation(participant_role="contributor").participant_role == "contributor"
    with pytest.raises(ValueError, match="expected work-package version is invalid"):
        _reservation(expected_package_version=0)
    with pytest.raises(ValueError, match="participant role is invalid"):
        _reservation(participant_role="observer")


def test_uuid_identity_is_preserved_on_a_reservation() -> None:
    reservation = _reservation()

    assert isinstance(reservation.package_id, UUID)
    assert reservation.package_id == PACKAGE
