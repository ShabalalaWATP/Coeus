from datetime import date

import pytest

from coeus.services import intake_extractors as extractors


@pytest.mark.parametrize(
    ("answer", "expected"),
    (
        ("all of 2025-2026", ("2025-01-01", "2026-12-31")),
        ("2025 to 2026", ("2025-01-01", "2026-12-31")),
        ("all of 2025", ("2025-01-01", "2025-12-31")),
        ("1st Jan 2025 to 30th Dec 2026", ("2025-01-01", "2026-12-30")),
        ("January 1, 2025 through December 30, 2026", ("2025-01-01", "2026-12-30")),
    ),
)
def test_natural_date_windows_are_normalised_to_iso_dates(
    answer: str, expected: tuple[str, str]
) -> None:
    assert extractors.extract_time_window(answer) == expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    (
        ("last year", ("2025-01-01", "2025-12-31")),
        ("this year", ("2026-01-01", "2026-12-31")),
        ("last month", ("2026-07-01", "2026-07-31")),
        ("this week", ("2026-07-27", "2026-08-02")),
    ),
)
def test_relative_windows_use_the_current_calendar_window(
    answer: str, expected: tuple[str, str]
) -> None:
    assert extractors.extract_time_window(answer, today=date(2026, 8, 1)) == expected


@pytest.mark.parametrize(
    "answer",
    (
        "all of 2026-2025",
        "31st February 2025 to 1st March 2025",
        "2026-02-01 to 2026-01-01",
    ),
)
def test_invalid_or_reversed_natural_ranges_are_rejected(answer: str) -> None:
    assert extractors.extract_time_window(answer) == (None, None)
    assert extractors.contains_explicit_date_range(answer)
