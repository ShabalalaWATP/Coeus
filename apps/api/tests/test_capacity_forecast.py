from datetime import UTC, datetime, timedelta

import pytest

from coeus.domain.capacity_forecast import CapacityForecast, CapacityInterval, forecast_capacity

START = datetime(2026, 8, 3, 8, tzinfo=UTC)


def _interval(start_hours: float, end_hours: float) -> CapacityInterval:
    return CapacityInterval(
        START + timedelta(hours=start_hours),
        START + timedelta(hours=end_hours),
    )


def test_forecast_unions_overlaps_and_conserves_capacity() -> None:
    result = forecast_capacity(
        (_interval(0, 8),),
        (_interval(1, 3), _interval(2, 4)),
        (_interval(3, 5), _interval(4, 6)),
        reservation_minutes=120,
        policy_buffer_minutes=30,
    )
    assert result == CapacityForecast(480, 180, 120, 120, 30, 30)


def test_forecast_unions_working_intervals_and_clamps_at_zero() -> None:
    result = forecast_capacity(
        (_interval(0, 4), _interval(2, 8)),
        (),
        (),
        reservation_minutes=600,
        policy_buffer_minutes=0,
    )
    assert result.physical_minutes == 480
    assert result.assignable_minutes == 0


def test_forecast_does_not_double_count_commitment_during_absence() -> None:
    result = forecast_capacity(
        (_interval(0, 8),),
        (_interval(0, 2),),
        (_interval(1, 3),),
        reservation_minutes=0,
        policy_buffer_minutes=0,
    )
    assert result.unavailable_minutes == 120
    assert result.commitment_minutes == 60
    assert result.assignable_minutes == 300


def test_touching_and_disjoint_intervals_remain_valid() -> None:
    result = forecast_capacity(
        (_interval(0, 1), _interval(1, 2), _interval(3, 4)),
        (_interval(8, 9),),
        (_interval(2, 3),),
        0,
        0,
    )
    assert result.physical_minutes == 180
    assert result.assignable_minutes == 180


@pytest.mark.parametrize(
    "start,end,message",
    [
        (START, START, "end"),
        (START.replace(tzinfo=None), (START + timedelta(hours=1)).replace(tzinfo=None), "timezone"),
    ],
)
def test_interval_validation(start: datetime, end: datetime, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        CapacityInterval(start, end)


def test_forecast_and_result_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="negative"):
        forecast_capacity((_interval(0, 1),), (), (), -1, 0)
    with pytest.raises(ValueError, match="15-minute"):
        forecast_capacity((_interval(0, 1),), (), (), 1, 0)
    with pytest.raises(ValueError, match="non-negative"):
        CapacityForecast(60, 0, 0, 0, 0, -15)
    with pytest.raises(ValueError, match="physical"):
        CapacityForecast(60, 0, 0, 0, 0, 75)


def test_partial_minutes_are_floored_to_a_quarter_hour() -> None:
    result = forecast_capacity(
        (CapacityInterval(START, START + timedelta(minutes=61)),),
        (),
        (),
        0,
        0,
    )
    assert result.assignable_minutes == 60
