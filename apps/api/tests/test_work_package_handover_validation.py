"""Evidence checks that guard a work-package handover before it commits."""

from uuid import UUID, uuid4

import pytest

from coeus.domain.work_package_handovers import (
    ReservationDisposition,
    ReservationHandover,
    WorkPackageHandoverConflict,
    WorkPackageHandoverDenied,
    WorkPackageHandoverRequest,
)
from coeus.persistence.work_package_handover_validation import (
    _validate_package,
    _validate_package_scope,
    _validate_participants,
    _validate_reservations,
)

UNIT, OWNER, TARGET = uuid4(), uuid4(), uuid4()
DIGEST = "a" * 64


def _request(*reservations: ReservationHandover, **overrides: object) -> WorkPackageHandoverRequest:
    values: dict[str, object] = {
        "unit_id": UNIT,
        "package_id": uuid4(),
        "target_user_id": TARGET,
        "expected_package_version": 1,
        "expected_ownership_version": 1,
        "authorising_grant_id": uuid4(),
        "expected_grant_version": 1,
        "target_membership_id": uuid4(),
        "expected_target_membership_version": 1,
        "expected_target_account_credential_version": 0,
        "expected_target_account_source_hash": DIGEST,
        "expected_ticket_version": 1,
        "expected_ticket_source_hash": DIGEST,
        "reservations": reservations,
    }
    values.update(overrides)
    return WorkPackageHandoverRequest(**values)  # type: ignore[arg-type]


def _package(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "owning_unit_id": UNIT,
        "ownership_unit_id": UNIT,
        "version": 1,
        "ownership_version": 1,
        "ownership_state": "active",
        "state": "in_progress",
        "accountable_user_id": OWNER,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize("field", ["owning_unit_id", "ownership_unit_id"])
def test_a_package_outside_the_requested_unit_is_unavailable(field: str) -> None:
    with pytest.raises(WorkPackageHandoverDenied, match="work package is unavailable"):
        _validate_package_scope(_request(), _package(**{field: uuid4()}))  # type: ignore[arg-type]


def test_a_package_inside_the_requested_unit_passes_the_scope_check() -> None:
    _validate_package_scope(_request(), _package())  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["version", "ownership_version"])
def test_stale_package_or_ownership_evidence_is_a_conflict(field: str) -> None:
    with pytest.raises(WorkPackageHandoverConflict, match="work-package evidence changed"):
        _validate_package(_request(), _package(**{field: 5}))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"ownership_state": "ended"},
        {"state": "complete"},
        {"accountable_user_id": None},
    ],
)
def test_an_unowned_or_closed_package_cannot_be_handed_over(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(WorkPackageHandoverDenied, match="work package is unavailable"):
        _validate_package(_request(), _package(**overrides))  # type: ignore[arg-type]


def test_handing_a_package_to_its_current_owner_is_refused() -> None:
    with pytest.raises(WorkPackageHandoverConflict, match="already the accountable owner"):
        _validate_package(_request(), _package(accountable_user_id=TARGET))  # type: ignore[arg-type]


def test_a_live_open_package_with_a_different_owner_is_accepted() -> None:
    _validate_package(_request(), _package())  # type: ignore[arg-type]


def _participant(
    user_id: UUID, role: str = "accountable", active: bool = True
) -> dict[str, object]:
    return {"user_id": user_id, "role": role, "active": active}


@pytest.mark.parametrize(
    "participants",
    [
        (),
        (_participant(OWNER), _participant(uuid4())),
        (_participant(uuid4()),),
        (_participant(OWNER, active=False),),
    ],
)
def test_the_package_must_show_exactly_one_matching_accountable_participant(
    participants: tuple[dict[str, object], ...],
) -> None:
    with pytest.raises(WorkPackageHandoverConflict, match="accountable participant evidence"):
        _validate_participants(_package(), _request(), participants)  # type: ignore[arg-type]


def test_a_target_already_recorded_as_accountable_is_refused() -> None:
    # A second active accountable row is caught by the cardinality check first,
    # so the dedicated target message is not reachable through this path.
    participants = (_participant(OWNER), _participant(TARGET))

    with pytest.raises(WorkPackageHandoverConflict, match="accountable participant evidence"):
        _validate_participants(_package(), _request(), participants)  # type: ignore[arg-type]


def test_a_contributing_target_does_not_block_the_handover() -> None:
    participants = (_participant(OWNER), _participant(TARGET, role="contributor"))

    _validate_participants(_package(), _request(), participants)  # type: ignore[arg-type]


def _reservation(
    reservation_id: UUID, user_id: UUID = OWNER, version: int = 1
) -> dict[str, object]:
    return {"reservation_id": reservation_id, "user_id": user_id, "version": version}


def _handover(reservation_id: UUID, version: int = 1) -> ReservationHandover:
    return ReservationHandover(reservation_id, version, ReservationDisposition.RELEASE)


def test_every_live_owner_reservation_needs_a_disposition() -> None:
    planned, unplanned = uuid4(), uuid4()
    request = _request(_handover(planned))

    with pytest.raises(WorkPackageHandoverConflict, match="needs a disposition"):
        _validate_reservations(
            _package(),  # type: ignore[arg-type]
            request,
            (_reservation(planned), _reservation(unplanned)),  # type: ignore[arg-type]
        )


def test_reservations_held_by_other_people_are_left_alone() -> None:
    planned = uuid4()
    request = _request(_handover(planned))

    source = _validate_reservations(
        _package(),  # type: ignore[arg-type]
        request,
        (_reservation(planned), _reservation(uuid4(), user_id=uuid4())),  # type: ignore[arg-type]
    )

    assert tuple(row["reservation_id"] for row in source) == (planned,)


def test_a_stale_source_reservation_version_is_a_conflict() -> None:
    planned = uuid4()
    request = _request(_handover(planned, version=1))

    with pytest.raises(WorkPackageHandoverConflict, match="source reservation evidence changed"):
        _validate_reservations(
            _package(),  # type: ignore[arg-type]
            request,
            (_reservation(planned, version=4),),  # type: ignore[arg-type]
        )


def test_an_oversized_reservation_inventory_is_refused_before_review() -> None:
    request = _request(_handover(uuid4()))
    reservations = tuple(_reservation(uuid4()) for _ in range(65))

    with pytest.raises(WorkPackageHandoverDenied, match="review boundary"):
        _validate_reservations(_package(), request, reservations)  # type: ignore[arg-type]
