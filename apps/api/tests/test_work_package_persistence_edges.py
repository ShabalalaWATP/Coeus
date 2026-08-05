from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from coeus.domain.capacity_forecast import CapacityInterval
from coeus.domain.enums import TicketState
from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.domain.tickets import (
    AnalystAssignment,
    AnalystWorkPackage,
    IntakeDetails,
    RoutingRoute,
    TicketRecord,
    WorkPackageStatus,
)
from coeus.domain.work_packages import (
    CapacityReservationConflict,
    CapacityUnknown,
    ReserveCapacityCommand,
)
from coeus.persistence.capacity_reservations_postgres import (
    _calendar_intervals,
    _exception_minutes,
    _existing,
    _request_hash,
    _validate_current_membership,
    _working_intervals,
    _working_pattern,
)
from coeus.persistence.work_package_projection_write import (
    _active_assignments,
    _lock_and_validate_memberships,
)
from coeus.persistence.work_package_status_write import sync_work_package_statuses

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


class _Result:
    def __init__(self, *, rows: tuple[dict[str, Any], ...] = (), scalar: Any = None) -> None:
        self.rows = rows
        self.scalar = scalar

    def mappings(self) -> "_Result":
        return self

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def scalar_one(self) -> Any:
        return self.scalar

    def scalar_one_or_none(self) -> Any:
        return self.scalar

    def __iter__(self):
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0)


def _ticket(*, assignments: tuple[AnalystAssignment, ...] = ()) -> TicketRecord:
    package = AnalystWorkPackage(
        uuid4(), uuid4(), "Assess synthetic reporting", WorkPackageStatus.PENDING, 1, NOW
    )
    return TicketRecord(
        package.ticket_id,
        "TCK-EDGE",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(title="Synthetic task"),
        analyst_assignments=assignments,
        work_packages=(package,),
    )


def _assignment(ticket_id, user_id, unit_id) -> AnalystAssignment:
    return AnalystAssignment(uuid4(), ticket_id, user_id, uuid4(), RoutingRoute.RFA, NOW, unit_id)


def _command() -> ReserveCapacityCommand:
    return ReserveCapacityCommand(
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        WorkflowLeg.RFA,
        uuid4(),
        NOW,
        NOW + timedelta(hours=4),
        60,
        "edge-capacity",
        1,
    )


def _pattern(**changes: Any) -> dict[str, Any]:
    value = {"time_zone": "Europe/London"}
    value.update(
        {
            f"{day}_minutes": 480
            for day in (
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            )
        }
    )
    value.update(changes)
    return value


def test_assignment_projection_rejects_missing_duplicate_and_ineligible_owners() -> None:
    unit_id, user_id = uuid4(), uuid4()
    ticket = _ticket()
    intent = AssignmentOwnershipIntent(unit_id, WorkflowLeg.RFA, uuid4(), uuid4())
    with pytest.raises(ValueError, match="active assignment"):
        _active_assignments(ticket, intent)
    assignment = _assignment(ticket.ticket_id, user_id, unit_id)
    duplicate = replace(assignment, assignment_id=uuid4())
    with pytest.raises(ValueError, match="duplicate"):
        _active_assignments(replace(ticket, analyst_assignments=(assignment, duplicate)), intent)
    with pytest.raises(ValueError, match="leaf delivery"):
        _lock_and_validate_memberships(_Connection(_Result()), (assignment,), unit_id, NOW)  # type: ignore[arg-type]
    connection = _Connection(
        _Result(scalar=unit_id),
        _Result(rows=({"unit_id": uuid4(), "assignment_eligible": True},)),
    )
    with pytest.raises(ValueError, match="eligible home"):
        _lock_and_validate_memberships(connection, (assignment,), unit_id, NOW)  # type: ignore[arg-type]


def test_package_status_sync_handles_empty_missing_unchanged_and_dependency_block() -> None:
    empty = replace(_ticket(), work_packages=())
    assert sync_work_package_statuses(_Connection(), empty, uuid4()) == ()  # type: ignore[arg-type]
    ticket = _ticket()
    missing = _Connection(_Result(scalar=NOW), _Result())
    assert sync_work_package_statuses(missing, ticket, uuid4()) == ()  # type: ignore[arg-type]
    package = ticket.work_packages[0]
    unchanged = _Connection(
        _Result(scalar=NOW),
        _Result(rows=({"state": "pending", "title": package.title, "version": 1},)),
    )
    assert sync_work_package_statuses(unchanged, ticket, uuid4()) == ()  # type: ignore[arg-type]
    completed_package = replace(package, status=WorkPackageStatus.COMPLETE)
    completed = replace(ticket, work_packages=(completed_package,))
    blocked = _Connection(
        _Result(scalar=NOW),
        _Result(rows=({"state": "pending", "title": package.title, "version": 1},)),
        _Result(scalar=1),
    )
    with pytest.raises(ValueError, match="dependencies"):
        sync_work_package_statuses(blocked, completed, uuid4())  # type: ignore[arg-type]


def test_capacity_helpers_fail_closed_for_missing_authority_and_calendar_expansion() -> None:
    command = _command()
    package = {"owning_unit_id": uuid4()}
    with pytest.raises(CapacityUnknown, match="home membership"):
        _validate_current_membership(_Connection(_Result()), command, package)  # type: ignore[arg-type]
    with pytest.raises(CapacityUnknown, match="working pattern"):
        _working_pattern(_Connection(_Result()), command)  # type: ignore[arg-type]
    recurring = _Connection(
        _Result(rows=({"recurrence_rule": {}, "starts_at": NOW, "ends_at": NOW},))
    )
    with pytest.raises(CapacityUnknown, match="invalid"):
        _calendar_intervals(recurring, command)  # type: ignore[arg-type]


def test_capacity_calendar_expands_all_day_leave_in_its_local_time_zone() -> None:
    command = _command()
    all_day = _Connection(
        _Result(
            rows=(
                {
                    "recurrence_rule": None,
                    "starts_at": None,
                    "ends_at": None,
                    "all_day_start": command.starts_at.date(),
                    "all_day_end": command.starts_at.date() + timedelta(days=1),
                    "time_zone": "Europe/London",
                },
            )
        )
    )
    intervals = _calendar_intervals(all_day, command)  # type: ignore[arg-type]
    assert intervals == (
        CapacityInterval(
            datetime(2026, 8, 2, 23, tzinfo=UTC),
            datetime(2026, 8, 3, 23, tzinfo=UTC),
        ),
    )

    invalid_zone = _Connection(
        _Result(
            rows=(
                {
                    "recurrence_rule": None,
                    "starts_at": None,
                    "ends_at": None,
                    "all_day_start": command.starts_at.date(),
                    "all_day_end": command.starts_at.date() + timedelta(days=1),
                    "time_zone": "Not/AZone",
                },
            )
        )
    )
    with pytest.raises(CapacityUnknown, match="time zone"):
        _calendar_intervals(invalid_zone, command)  # type: ignore[arg-type]

    dst_command = replace(
        command,
        starts_at=datetime(2026, 3, 29, tzinfo=UTC),
        ends_at=datetime(2026, 3, 30, tzinfo=UTC),
    )
    dst_day = _Connection(
        _Result(
            rows=(
                {
                    "recurrence_rule": None,
                    "starts_at": None,
                    "ends_at": None,
                    "all_day_start": dst_command.starts_at.date(),
                    "all_day_end": dst_command.ends_at.date(),
                    "time_zone": "Europe/London",
                },
            )
        )
    )
    assert _calendar_intervals(dst_day, dst_command) == (  # type: ignore[arg-type]
        CapacityInterval(
            datetime(2026, 3, 29, tzinfo=UTC),
            datetime(2026, 3, 29, 23, tzinfo=UTC),
        ),
    )


def test_working_interval_and_exception_edges() -> None:
    with pytest.raises(CapacityUnknown, match="time zone"):
        _working_intervals(_pattern(time_zone="Not/AZone"), NOW, NOW + timedelta(hours=1))
    with pytest.raises(CapacityUnknown, match="no capacity"):
        _working_intervals(
            _pattern(
                **{
                    f"{day}_minutes": 0
                    for day in (
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    )
                }
            ),
            NOW,
            NOW + timedelta(hours=1),
        )
    command = _command()
    connection = _Connection(
        _Result(
            rows=(
                {"reduction_minutes": 30, "reduction_percent": None},
                {"reduction_minutes": None, "reduction_percent": Decimal("10")},
            )
        )
    )
    assert _exception_minutes(connection, command, 300) == 60  # type: ignore[arg-type]
    assert _request_hash(command) == _request_hash(command)
    assert _request_hash(command) != _request_hash(replace(command, reserved_minutes=75))


def test_capacity_identity_lookup_rejects_split_key_and_reservation_rows() -> None:
    command = _command()
    with pytest.raises(CapacityReservationConflict, match="identities conflict"):
        _existing(
            _Connection(
                _Result(
                    rows=(
                        {"reservation_id": command.reservation_id},
                        {"reservation_id": uuid4()},
                    )
                )
            ),  # type: ignore[arg-type]
            command,
        )
    assert _existing(_Connection(_Result()), command) is None  # type: ignore[arg-type]
