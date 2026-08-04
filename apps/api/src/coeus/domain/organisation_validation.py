"""Shared scalar validation for organisation authority records."""

from datetime import UTC, datetime


def aware(value: datetime | None, field_name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field_name} must be timezone-aware")
    if value is not None:
        value.astimezone(UTC)


def interval(start: datetime, end: datetime | None) -> None:
    aware(start, "valid_from")
    aware(end, "valid_until")
    if end is not None and end <= start:
        raise ValueError("valid_until must be later than valid_from")


def text_value(value: str, field_name: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"{field_name} must contain 1 to {maximum} trimmed characters")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} cannot contain control characters")


def optional_text(value: str, field_name: str, maximum: int) -> None:
    if value:
        text_value(value, field_name, maximum)
