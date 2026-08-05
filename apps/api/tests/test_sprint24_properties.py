"""Property evidence for Sprint 24 structural and capacity invariants."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coeus.domain.calendar_recurrence import expand_occurrences
from coeus.domain.capacity_forecast import CapacityInterval, forecast_capacity
from coeus.domain.organisation import MAX_ORGANISATION_DEPTH, OrganisationTopologyRevision
from coeus.domain.workforce_calendar import (
    CalendarFrequency,
    CalendarRecurrence,
    CalendarTiming,
)


def _uuid(value: int) -> UUID:
    return UUID(int=value + 1)


def _interval(hour: int, duration_hours: int) -> CapacityInterval:
    starts_at = datetime(2026, 1, 5, hour, tzinfo=UTC)
    return CapacityInterval(starts_at, starts_at + timedelta(hours=duration_hours))


def test_documented_capacity_conservation_example_is_exact() -> None:
    result = forecast_capacity(
        working=(_interval(8, 8),),
        unavailable=(_interval(9, 2),),
        commitments=(_interval(12, 1),),
        reservation_minutes=120,
        policy_buffer_minutes=0,
    )

    assert result.physical_minutes == 480
    assert result.unavailable_minutes == 120
    assert result.commitment_minutes == 60
    assert result.reservation_minutes == 120
    assert result.assignable_minutes == 180


@st.composite
def _quarter_hour_intervals(
    draw: st.DrawFn, *, max_count: int = 12
) -> tuple[CapacityInterval, ...]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    values = draw(
        st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=31),
                st.integers(min_value=1, max_value=16),
            ),
            max_size=max_count,
        )
    )
    return tuple(
        CapacityInterval(
            base + timedelta(minutes=start * 15),
            base + timedelta(minutes=(start + length) * 15),
        )
        for start, length in values
    )


@given(
    working=_quarter_hour_intervals(),
    unavailable=_quarter_hour_intervals(),
    commitments=_quarter_hour_intervals(),
    reservations=st.integers(min_value=0, max_value=32).map(lambda value: value * 15),
    buffer=st.integers(min_value=0, max_value=16).map(lambda value: value * 15),
)
def test_capacity_is_conserved_and_permutation_invariant(
    working: tuple[CapacityInterval, ...],
    unavailable: tuple[CapacityInterval, ...],
    commitments: tuple[CapacityInterval, ...],
    reservations: int,
    buffer: int,
) -> None:
    result = forecast_capacity(working, unavailable, commitments, reservations, buffer)
    reversed_result = forecast_capacity(
        tuple(reversed(working)),
        tuple(reversed(unavailable)),
        tuple(reversed(commitments)),
        reservations,
        buffer,
    )

    assert result == reversed_result
    assert 0 <= result.assignable_minutes <= result.physical_minutes
    assert result.unavailable_minutes <= result.physical_minutes
    assert result.commitment_minutes <= result.physical_minutes - result.unavailable_minutes
    assert result.assignable_minutes == max(
        0,
        result.physical_minutes
        - result.unavailable_minutes
        - result.commitment_minutes
        - reservations
        - buffer,
    )


@given(
    interval=st.integers(min_value=1, max_value=7),
    duration=st.integers(min_value=0, max_value=366),
    weekday_values=st.sets(st.integers(min_value=0, max_value=6), min_size=1, max_size=7),
    weekly=st.booleans(),
)
def test_recurrence_expansion_is_bounded_and_stable(
    interval: int,
    duration: int,
    weekday_values: set[int],
    weekly: bool,
) -> None:
    start = date(2026, 1, 1)
    timing = CalendarTiming(
        "Europe/London", all_day_start=start, all_day_end=start + timedelta(days=1)
    )
    recurrence = CalendarRecurrence(
        CalendarFrequency.WEEKLY if weekly else CalendarFrequency.DAILY,
        interval,
        start + timedelta(days=duration),
        tuple(sorted(weekday_values)) if weekly else (),
    )
    window_start = datetime(2025, 12, 31, tzinfo=UTC)
    window_end = datetime(2027, 1, 3, tzinfo=UTC)

    first = expand_occurrences(timing, recurrence, window_start, window_end)
    second = expand_occurrences(timing, recurrence, window_start, window_end)

    assert first == second
    assert len(first) <= 500
    assert len({item.occurrence_key for item in first}) == len(first)
    assert all(
        start <= date.fromisoformat(item.occurrence_key) <= recurrence.until for item in first
    )


@given(depth=st.integers(min_value=0, max_value=MAX_ORGANISATION_DEPTH))
def test_unique_topology_paths_preserve_acyclicity(depth: int) -> None:
    path = tuple(_uuid(index) for index in range(depth + 1))
    revision = OrganisationTopologyRevision(
        revision_id=_uuid(100),
        unit_id=path[-1],
        parent_unit_id=path[-2] if depth else None,
        path=path,
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        change_command_id=_uuid(101),
        changed_by_user_id=_uuid(102),
    )

    assert revision.path == path


@given(depth=st.integers(min_value=1, max_value=MAX_ORGANISATION_DEPTH))
def test_repeated_topology_node_is_always_rejected(depth: int) -> None:
    unique = tuple(_uuid(index) for index in range(depth))
    path = (*unique, unique[0])

    with pytest.raises(ValueError, match="cycle"):
        OrganisationTopologyRevision(
            revision_id=_uuid(100),
            unit_id=path[-1],
            parent_unit_id=path[-2],
            path=path,
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            change_command_id=_uuid(101),
            changed_by_user_id=_uuid(102),
        )
