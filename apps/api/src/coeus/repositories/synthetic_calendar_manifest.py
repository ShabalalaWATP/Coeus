"""Bounded calendar scenarios for the relational exercise workforce."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEventSource,
    CalendarPrivacy,
)
from coeus.repositories.synthetic_organisation_manifest import BASELINE


@dataclass(frozen=True)
class SyntheticCalendarEventSpec:
    key: str
    owner_username: str
    created_by_username: str
    unit_key: str
    source: CalendarEventSource
    activity: CalendarActivity
    availability: AvailabilityEffect
    privacy: CalendarPrivacy
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day_start: date | None = None
    all_day_end: date | None = None
    manager_scope_unit_key: str | None = None

    @property
    def event_id(self) -> UUID:
        return uuid5(NAMESPACE_URL, f"coeus:synthetic-calendar-event:v2:{self.key}")

    def scope_id(self, scope_type: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"coeus:synthetic-calendar-scope:v2:{self.key}:{scope_type}",
        )

    @property
    def history_id(self) -> UUID:
        return uuid5(NAMESPACE_URL, f"coeus:synthetic-calendar-history:v2:{self.key}")

    @property
    def command_id(self) -> UUID:
        return uuid5(NAMESPACE_URL, f"coeus:synthetic-calendar-command:v2:{self.key}")


def synthetic_calendar_events() -> tuple[SyntheticCalendarEventSpec, ...]:
    return (
        _all_day("rfa-leave", "analyst.2@example.test", "rfa_maritime", 7, 2),
        _timed(
            "rfa-training",
            "analyst.5@example.test",
            "rfa_land",
            1,
            9,
            17,
            CalendarActivity.TRAINING,
            AvailabilityEffect.UNAVAILABLE,
        ),
        _timed(
            "rfa-manager-duty",
            "analyst.6@example.test",
            "rfa_land",
            2,
            8,
            12,
            CalendarActivity.DUTY,
            AvailabilityEffect.PARTIAL,
            source=CalendarEventSource.MANAGER,
            created_by="rfa.lead.2@example.test",
        ),
        _timed(
            "rfa-private-appointment",
            "analyst.8@example.test",
            "rfa_cyber",
            3,
            10,
            11,
            CalendarActivity.APPOINTMENT,
            AvailabilityEffect.UNAVAILABLE,
            privacy=CalendarPrivacy.PRIVATE,
        ),
        _timed(
            "rfa-team-meeting",
            "analyst.11@example.test",
            "rfa_regional",
            4,
            13,
            15,
            CalendarActivity.MEETING,
            AvailabilityEffect.PARTIAL,
        ),
        _all_day("cm-leave", "analyst.16@example.test", "cm_open", 5, 1),
        _timed(
            "cm-imagery-training",
            "analyst.20@example.test",
            "cm_geo",
            6,
            9,
            15,
            CalendarActivity.TRAINING,
            AvailabilityEffect.UNAVAILABLE,
        ),
        _timed(
            "cm-requirements-duty",
            "analyst.22@example.test",
            "cm_requirements",
            8,
            8,
            16,
            CalendarActivity.DUTY,
            AvailabilityEffect.UNAVAILABLE,
        ),
    )


def _all_day(
    key: str,
    username: str,
    unit_key: str,
    offset_days: int,
    duration_days: int,
) -> SyntheticCalendarEventSpec:
    start = (BASELINE + timedelta(days=offset_days)).date()
    return SyntheticCalendarEventSpec(
        key,
        username,
        username,
        unit_key,
        CalendarEventSource.PERSONAL,
        CalendarActivity.LEAVE,
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.PRIVATE,
        all_day_start=start,
        all_day_end=start + timedelta(days=duration_days),
    )


def _timed(
    key: str,
    username: str,
    unit_key: str,
    offset_days: int,
    start_hour: int,
    end_hour: int,
    activity: CalendarActivity,
    availability: AvailabilityEffect,
    *,
    source: CalendarEventSource = CalendarEventSource.PERSONAL,
    created_by: str | None = None,
    privacy: CalendarPrivacy = CalendarPrivacy.TEAM_SUMMARY,
) -> SyntheticCalendarEventSpec:
    start = (BASELINE + timedelta(days=offset_days)).replace(hour=start_hour)
    end = (BASELINE + timedelta(days=offset_days)).replace(hour=end_hour)
    return SyntheticCalendarEventSpec(
        key,
        username,
        created_by or username,
        unit_key,
        source,
        activity,
        availability,
        privacy,
        starts_at=start,
        ends_at=end,
        manager_scope_unit_key=unit_key if source is CalendarEventSource.MANAGER else None,
    )
