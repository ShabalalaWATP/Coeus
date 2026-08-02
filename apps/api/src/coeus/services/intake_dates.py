"""Deterministic natural-language date windows for customer intake."""

import calendar
import re
from collections.abc import Callable
from datetime import date, timedelta

_JOINER = r"(?:to|through|until|\u2013|\u2014|-)"
_YEAR = r"(?:19\d{2}|20\d{2}|21\d{2})"
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)"
)

_ISO_RANGE = re.compile(
    rf"\b(?:from\s+)?(?P<start>\d{{4}}-\d{{2}}-\d{{2}})\s+{_JOINER}\s+"
    rf"(?P<end>\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)
_UK_RANGE = re.compile(
    rf"\b(?:from\s+)?(?P<start>\d{{1,2}}/\d{{1,2}}/\d{{2,4}})\s+{_JOINER}\s+"
    rf"(?P<end>\d{{1,2}}/\d{{1,2}}/\d{{2,4}})\b",
    re.IGNORECASE,
)
_DAY_FIRST_RANGE = re.compile(
    rf"\b(?:from\s+)?(?P<start_day>\d{{1,2}})(?:st|nd|rd|th)?\s+"
    rf"(?P<start_month>{_MONTH})\.?\s*,?\s*(?P<start_year>{_YEAR})\s+"
    rf"{_JOINER}\s+(?P<end_day>\d{{1,2}})(?:st|nd|rd|th)?\s+"
    rf"(?P<end_month>{_MONTH})\.?\s*,?\s*(?P<end_year>{_YEAR})\b",
    re.IGNORECASE,
)
_MONTH_FIRST_RANGE = re.compile(
    rf"\b(?:from\s+)?(?P<start_month>{_MONTH})\.?\s+"
    rf"(?P<start_day>\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*|\s+)"
    rf"(?P<start_year>{_YEAR})\s+{_JOINER}\s+"
    rf"(?P<end_month>{_MONTH})\.?\s+(?P<end_day>\d{{1,2}})"
    rf"(?:st|nd|rd|th)?(?:,\s*|\s+)(?P<end_year>{_YEAR})\b",
    re.IGNORECASE,
)
_YEAR_RANGE = re.compile(
    rf"\b(?:(?:the\s+)?(?:whole|entirety|all)\s+of\s+)?"
    rf"(?P<start>{_YEAR})\s*{_JOINER}\s*(?P<end>{_YEAR})\b",
    re.IGNORECASE,
)
_WHOLE_YEAR = re.compile(
    rf"\b(?:the\s+)?(?:whole|entirety|all)\s+of\s+(?P<year>{_YEAR})\b",
    re.IGNORECASE,
)
_RELATIVE_WINDOW = re.compile(
    r"\b(?P<direction>last|this|next)\s+(?P<unit>week|month|year)\b", re.I
)
_RELATIVE_DAY = re.compile(r"\b(?P<day>yesterday|today|tomorrow)\b", re.I)
_ROUGH_MONTH = re.compile(
    r"\b(?:the\s+)?(?:entirety|whole|all)\s+of\s+"
    r"(?:january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\b",
    re.IGNORECASE,
)

_MONTH_NUMBERS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_EXPLICIT_RANGE_PATTERNS = (
    _ISO_RANGE,
    _UK_RANGE,
    _DAY_FIRST_RANGE,
    _MONTH_FIRST_RANGE,
    _YEAR_RANGE,
)


def extract_time_window(text: str, *, today: date | None = None) -> tuple[str | None, str | None]:
    """Return an ISO date window when wording is concrete enough to resolve."""
    for pattern, parser in (
        (_ISO_RANGE, _parse_iso_range),
        (_UK_RANGE, _parse_uk_range),
        (_DAY_FIRST_RANGE, _parse_named_range),
        (_MONTH_FIRST_RANGE, _parse_named_range),
        (_YEAR_RANGE, _parse_year_range),
    ):
        matched = pattern.search(text)
        if matched is not None:
            return _validated_range(parser, matched)

    whole_year = _WHOLE_YEAR.search(text)
    if whole_year is not None:
        year = int(whole_year.group("year"))
        return f"{year:04d}-01-01", f"{year:04d}-12-31"

    reference = today or date.today()
    relative = _RELATIVE_WINDOW.search(text)
    if relative is not None:
        return _relative_window(reference, relative.group("direction"), relative.group("unit"))
    relative_day = _RELATIVE_DAY.search(text)
    if relative_day is not None:
        offset = {"yesterday": -1, "today": 0, "tomorrow": 1}[relative_day.group("day").casefold()]
        selected = reference + timedelta(days=offset)
        return selected.isoformat(), selected.isoformat()

    rough_month = _ROUGH_MONTH.search(text)
    if rough_month is not None:
        value = " ".join(rough_month.group(0).split()).strip()
        return value, value
    return None, None


def contains_explicit_date_range(text: str) -> bool:
    return any(pattern.search(text) is not None for pattern in _EXPLICIT_RANGE_PATTERNS)


def is_resolved_time_window(start: str | None, end: str | None) -> bool:
    if not start or not end:
        return False
    try:
        parsed_start = date.fromisoformat(start)
        parsed_end = date.fromisoformat(end)
    except ValueError:
        return False
    return parsed_start <= parsed_end


def _validated_range(
    parser: Callable[[re.Match[str]], tuple[date, date]], matched: re.Match[str]
) -> tuple[str | None, str | None]:
    try:
        start, end = parser(matched)
    except ValueError:
        return None, None
    if start > end:
        return None, None
    return start.isoformat(), end.isoformat()


def _parse_iso_range(matched: re.Match[str]) -> tuple[date, date]:
    return date.fromisoformat(matched.group("start")), date.fromisoformat(matched.group("end"))


def _parse_uk_range(matched: re.Match[str]) -> tuple[date, date]:
    return _uk_date(matched.group("start")), _uk_date(matched.group("end"))


def _parse_named_range(matched: re.Match[str]) -> tuple[date, date]:
    return _named_date(matched, "start"), _named_date(matched, "end")


def _parse_year_range(matched: re.Match[str]) -> tuple[date, date]:
    start_year = int(matched.group("start"))
    end_year = int(matched.group("end"))
    return date(start_year, 1, 1), date(end_year, 12, 31)


def _uk_date(value: str) -> date:
    day, month, year = (int(part) for part in value.split("/"))
    return date(year + 2000 if year < 100 else year, month, day)


def _named_date(matched: re.Match[str], prefix: str) -> date:
    month_name = matched.group(f"{prefix}_month").casefold()[:3]
    return date(
        int(matched.group(f"{prefix}_year")),
        _MONTH_NUMBERS[month_name],
        int(matched.group(f"{prefix}_day")),
    )


def _relative_window(reference: date, direction: str, unit: str) -> tuple[str, str]:
    offset = {"last": -1, "this": 0, "next": 1}[direction.casefold()]
    normalised_unit = unit.casefold()
    if normalised_unit == "year":
        year = reference.year + offset
        start, end = date(year, 1, 1), date(year, 12, 31)
    elif normalised_unit == "month":
        month_index = reference.year * 12 + reference.month - 1 + offset
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
    else:
        start = reference - timedelta(days=reference.weekday()) + timedelta(weeks=offset)
        end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()
