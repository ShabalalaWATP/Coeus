"""Deterministic, overlap-safe personal capacity arithmetic."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, order=True)
class CapacityInterval:
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("capacity intervals must be timezone-aware")
        if self.starts_at >= self.ends_at:
            raise ValueError("capacity interval end must follow its start")


@dataclass(frozen=True)
class CapacityForecast:
    physical_minutes: int
    unavailable_minutes: int
    commitment_minutes: int
    reservation_minutes: int
    policy_buffer_minutes: int
    assignable_minutes: int

    def __post_init__(self) -> None:
        values = (
            self.physical_minutes,
            self.unavailable_minutes,
            self.commitment_minutes,
            self.reservation_minutes,
            self.policy_buffer_minutes,
            self.assignable_minutes,
        )
        if any(value < 0 or value % 15 for value in values):
            raise ValueError("capacity values must use non-negative 15-minute increments")
        if self.assignable_minutes > self.physical_minutes:
            raise ValueError("assignable capacity cannot exceed physical capacity")


def forecast_capacity(
    working: tuple[CapacityInterval, ...],
    unavailable: tuple[CapacityInterval, ...],
    commitments: tuple[CapacityInterval, ...],
    reservation_minutes: int,
    policy_buffer_minutes: int,
) -> CapacityForecast:
    """Union overlapping time before subtracting each class of commitment once."""
    if reservation_minutes < 0 or policy_buffer_minutes < 0:
        raise ValueError("capacity deductions cannot be negative")
    if reservation_minutes % 15 or policy_buffer_minutes % 15:
        raise ValueError("capacity deductions must use 15-minute increments")
    physical = _floor_quarter_hour(_minutes(_union(working)))
    unavailable_overlap = _intersection_minutes(working, unavailable)
    available_work = _subtract(working, unavailable)
    commitment_overlap = _intersection_minutes(available_work, commitments)
    assignable = max(
        0,
        physical
        - unavailable_overlap
        - commitment_overlap
        - reservation_minutes
        - policy_buffer_minutes,
    )
    return CapacityForecast(
        physical,
        unavailable_overlap,
        commitment_overlap,
        reservation_minutes,
        policy_buffer_minutes,
        min(physical, _floor_quarter_hour(assignable)),
    )


def _intersection_minutes(
    bases: tuple[CapacityInterval, ...], deductions: tuple[CapacityInterval, ...]
) -> int:
    intersections = tuple(
        CapacityInterval(
            max(base.starts_at, deduction.starts_at),
            min(base.ends_at, deduction.ends_at),
        )
        for base in _union(bases)
        for deduction in _union(deductions)
        if max(base.starts_at, deduction.starts_at) < min(base.ends_at, deduction.ends_at)
    )
    return _floor_quarter_hour(_minutes(_union(intersections)))


def _subtract(
    bases: tuple[CapacityInterval, ...], deductions: tuple[CapacityInterval, ...]
) -> tuple[CapacityInterval, ...]:
    remaining = list(_union(bases))
    for deduction in _union(deductions):
        next_remaining: list[CapacityInterval] = []
        for base in remaining:
            if deduction.ends_at <= base.starts_at or deduction.starts_at >= base.ends_at:
                next_remaining.append(base)
                continue
            if base.starts_at < deduction.starts_at:
                next_remaining.append(CapacityInterval(base.starts_at, deduction.starts_at))
            if deduction.ends_at < base.ends_at:
                next_remaining.append(CapacityInterval(deduction.ends_at, base.ends_at))
        remaining = next_remaining
    return tuple(remaining)


def _union(intervals: tuple[CapacityInterval, ...]) -> tuple[CapacityInterval, ...]:
    if not intervals:
        return ()
    merged: list[CapacityInterval] = []
    for interval in sorted(intervals):
        if not merged or interval.starts_at > merged[-1].ends_at:
            merged.append(interval)
            continue
        previous = merged[-1]
        merged[-1] = CapacityInterval(previous.starts_at, max(previous.ends_at, interval.ends_at))
    return tuple(merged)


def _minutes(intervals: tuple[CapacityInterval, ...]) -> int:
    return int(sum((item.ends_at - item.starts_at).total_seconds() for item in intervals) // 60)


def _floor_quarter_hour(minutes: int) -> int:
    return minutes - minutes % 15
