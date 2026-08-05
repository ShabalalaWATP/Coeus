"""Shared workforce-calendar enum values."""

from enum import StrEnum


class CalendarEventSource(StrEnum):
    PERSONAL = "personal"
    MANAGER = "manager"
    TEAM = "team"
    TASK = "task"
    EXTERNAL = "external"
    LEGACY = "legacy"


class CalendarActivity(StrEnum):
    LEAVE = "leave"
    TRAINING = "training"
    DUTY = "duty"
    APPOINTMENT = "appointment"
    MEETING = "meeting"
    TASK = "task"
    OTHER = "other"


class AvailabilityEffect(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class CalendarPrivacy(StrEnum):
    PRIVATE = "private"
    TEAM_SUMMARY = "team_summary"
    TEAM_DETAIL = "team_detail"


class CalendarEventStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    CONFLICTED = "conflicted"


class CalendarMutationOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    CANCEL = "cancel"
    UPDATE_OCCURRENCE = "update_occurrence"
    CANCEL_OCCURRENCE = "cancel_occurrence"
    UPDATE_FUTURE = "update_future"


class CalendarFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
