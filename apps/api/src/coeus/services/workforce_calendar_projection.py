"""Privacy-safe direct and descendant workforce-calendar projections."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from coeus.application.ports.access import UserLookup
from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.workforce_calendar import WorkforceCalendarStore
from coeus.domain.calendar_deduplication import deduplicate_occurrences
from coeus.domain.calendar_recurrence import expand_event
from coeus.domain.organisation import ManagementAction, MembershipState
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarAggregateCell,
    CalendarEvent,
    CalendarPrivacy,
    CalendarProjection,
    CalendarProjectionDenied,
    CalendarProjectionDetail,
    CalendarProjectionEntry,
    CalendarProjectionScope,
    CalendarRecurrenceIntegrityError,
    CalendarTiming,
    ScopedCalendarOccurrence,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator

_DIRECT_WINDOW_DAYS = 92
_DESCENDANT_WINDOW_DAYS = 31
_PAGE_SIZE = 100
_SMALL_COUNT = 5


class WorkforceCalendarProjectionService:
    """Build bounded projections without turning hierarchy into implicit access."""

    def __init__(
        self,
        organisation: OrganisationReader,
        users: UserLookup,
        store: WorkforceCalendarStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._organisation = organisation
        self._users = users
        self._store = store
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))

    def project(
        self,
        actor_user_id: UUID,
        root_unit_id: UUID,
        window_start: datetime,
        window_end: datetime,
        *,
        include_descendants: bool,
        request_detail: bool,
    ) -> CalendarProjection:
        now = self._clock()
        self._validate_window(window_start, window_end, include_descendants)
        root = self._organisation.get_unit(root_unit_id)
        if root is None or not root.is_active:
            raise CalendarProjectionDenied("calendar scope is not available")
        action = (
            ManagementAction.CALENDAR_VIEW_DETAIL
            if request_detail
            else ManagementAction.CALENDAR_VIEW_AVAILABILITY
        )
        grant_id = self._projection_grant(
            actor_user_id, root_unit_id, action, now, include_descendants
        )
        if grant_id is None:
            raise CalendarProjectionDenied("calendar projection authority is unavailable")
        descendants = (
            self._organisation.list_descendants(root_unit_id, maximum_depth=12, limit=1_000)
            if include_descendants
            else ()
        )
        unit_ids = (root_unit_id, *(unit.unit_id for unit in descendants))
        member_units = self._current_member_units(unit_ids, now)
        ambiguous = {user_id for user_id, units in member_units.items() if len(units) != 1}
        member_count = len(member_units) - len(ambiguous)
        scoped = self._store.list_unit_events(
            actor_user_id,
            grant_id,
            action,
            root_unit_id,
            unit_ids,
            window_start,
            window_end,
        )
        seeds = tuple(
            item
            for item in scoped
            if item.event.source.value == "team"
            or (
                item.event.owner_user_id in member_units
                and item.unit_id in member_units[item.event.owner_user_id]
                and item.event.owner_user_id not in ambiguous
            )
        )
        try:
            expanded = tuple(
                ScopedCalendarOccurrence(item.unit_id, occurrence)
                for item in seeds
                for occurrence in expand_event(item.event, window_start, window_end)
            )
            eligible = tuple(
                sorted(
                    _deduplicate_scoped(expanded),
                    key=lambda item: (
                        item.occurrence.event.timing.starts_at
                        or datetime.combine(
                            item.occurrence.event.timing.all_day_start or date.min,
                            time.min,
                            UTC,
                        ),
                    ),
                )[: _PAGE_SIZE + 1]
            )
        except ValueError as exc:
            raise CalendarRecurrenceIntegrityError(
                "stored calendar recurrence cannot be expanded"
            ) from exc
        entries = self._entries(eligible, actor_user_id, include_descendants, request_detail)
        aggregates = (
            self._aggregates(
                eligible,
                root_unit_id,
                root.time_zone,
                window_start,
                window_end,
                member_count,
                incomplete=len(eligible) > _PAGE_SIZE,
            )
            if include_descendants and not request_detail
            else ()
        )
        suppressed = include_descendants and (
            member_count < _SMALL_COUNT or any(cell.suppressed for cell in aggregates)
        )
        generated_at = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        return CalendarProjection(
            root_unit_id=root_unit_id,
            scope=(
                CalendarProjectionScope.DESCENDANTS
                if include_descendants
                else CalendarProjectionScope.DIRECT
            ),
            generated_at=generated_at,
            unit_ids=unit_ids,
            member_count=None if suppressed else member_count,
            suppressed=suppressed,
            truncated=len(eligible) > _PAGE_SIZE,
            entries=entries,
            aggregates=aggregates,
        )

    def _projection_grant(
        self,
        actor_user_id: UUID,
        root_unit_id: UUID,
        action: ManagementAction,
        effective_at: datetime,
        include_descendants: bool,
    ) -> UUID | None:
        decision = self._scope.evaluate(actor_user_id, root_unit_id, action, effective_at)
        grant_id = decision.evidence_grant_id
        if not decision.allowed or grant_id is None:
            return None
        grant = self._organisation.get_management_grant(grant_id)
        if grant is None or (include_descendants and not grant.include_descendants):
            return None
        return grant_id

    def _current_member_units(
        self, unit_ids: tuple[UUID, ...], effective_at: datetime
    ) -> dict[UUID, set[UUID]]:
        members: dict[UUID, set[UUID]] = {}
        for unit_id in unit_ids:
            for membership in self._organisation.list_unit_memberships(unit_id, limit=500):
                if not (
                    membership.state is MembershipState.ACTIVE
                    and membership.valid_from <= effective_at
                    and (membership.valid_until is None or effective_at < membership.valid_until)
                ):
                    continue
                user = self._users.get_user(membership.user_id)
                if user is not None and user.is_active:
                    members.setdefault(membership.user_id, set()).add(unit_id)
        return members

    @staticmethod
    def _entries(
        events: tuple[ScopedCalendarOccurrence, ...],
        actor_user_id: UUID,
        include_descendants: bool,
        request_detail: bool,
    ) -> tuple[CalendarProjectionEntry, ...]:
        if include_descendants and not request_detail:
            return ()
        return tuple(
            _project_entry(item, actor_user_id, request_detail) for item in events[:_PAGE_SIZE]
        )

    @staticmethod
    def _aggregates(
        events: tuple[ScopedCalendarOccurrence, ...],
        root_unit_id: UUID,
        time_zone: str,
        window_start: datetime,
        window_end: datetime,
        member_count: int,
        *,
        incomplete: bool,
    ) -> tuple[CalendarAggregateCell, ...]:
        zone = ZoneInfo(time_zone)
        first_day = window_start.astimezone(zone).date()
        final_day = (window_end - timedelta(microseconds=1)).astimezone(zone).date()
        cells: list[CalendarAggregateCell] = []
        day = first_day
        while day <= final_day:
            unavailable = {
                item.occurrence.event.owner_user_id
                for item in events
                if item.occurrence.event.availability is not AvailabilityEffect.AVAILABLE
                and _event_overlaps_day(item.occurrence.event, day, zone)
            }
            small_cohort = member_count < _SMALL_COUNT
            small_value = 0 < len(unavailable) < _SMALL_COUNT
            hide_value = incomplete or small_cohort or small_value
            cells.append(
                CalendarAggregateCell(
                    root_unit_id,
                    day,
                    None if small_cohort else member_count,
                    None if hide_value else len(unavailable),
                    hide_value,
                )
            )
            day += timedelta(days=1)
        return tuple(cells)

    @staticmethod
    def _validate_window(
        window_start: datetime, window_end: datetime, include_descendants: bool
    ) -> None:
        if window_end <= window_start:
            raise ValueError("calendar window end must follow its start")
        maximum = _DESCENDANT_WINDOW_DAYS if include_descendants else _DIRECT_WINDOW_DAYS
        if window_end - window_start > timedelta(days=maximum):
            raise ValueError(f"calendar projection window cannot exceed {maximum} days")


def _project_entry(
    scoped: ScopedCalendarOccurrence, actor_user_id: UUID, detail_requested: bool
) -> CalendarProjectionEntry:
    event = scoped.occurrence.event
    identity = (scoped.occurrence.series_event_id, scoped.occurrence.occurrence_key)
    if detail_requested and event.owner_user_id == actor_user_id:
        return CalendarProjectionEntry(
            scoped.unit_id,
            event.timing,
            event.availability,
            CalendarProjectionDetail.SELF,
            event.event_id,
            event.owner_user_id,
            event.activity,
            event.note,
            *identity,
        )
    if not detail_requested:
        return CalendarProjectionEntry(
            scoped.unit_id,
            _coarse_timing(event),
            event.availability,
            CalendarProjectionDetail.AVAILABILITY,
            series_event_id=identity[0],
            occurrence_key=identity[1],
        )
    if event.privacy is CalendarPrivacy.TEAM_DETAIL:
        return CalendarProjectionEntry(
            scoped.unit_id,
            event.timing,
            event.availability,
            CalendarProjectionDetail.DETAIL,
            owner_user_id=event.owner_user_id,
            activity=event.activity,
            note=event.note,
            series_event_id=identity[0],
            occurrence_key=identity[1],
        )
    return CalendarProjectionEntry(
        scoped.unit_id,
        _coarse_timing(event),
        event.availability,
        CalendarProjectionDetail.DETAIL,
        owner_user_id=event.owner_user_id,
        series_event_id=identity[0],
        occurrence_key=identity[1],
    )


def _coarse_timing(event: CalendarEvent) -> CalendarTiming:
    timing = event.timing
    if timing.all_day_start is not None and timing.all_day_end is not None:
        return timing
    start = timing.start_date
    end = (
        timing.ends_at.astimezone(ZoneInfo(timing.time_zone)).date()
        if timing.ends_at is not None
        else start
    )
    return CalendarTiming(
        timing.time_zone,
        all_day_start=start,
        all_day_end=max(start + timedelta(days=1), end + timedelta(days=1)),
    )


def _event_overlaps_day(event: CalendarEvent, day: date, zone: ZoneInfo) -> bool:
    timing = event.timing
    if timing.all_day_start is not None and timing.all_day_end is not None:
        return timing.all_day_start <= day < timing.all_day_end
    if timing.starts_at is None or timing.ends_at is None:
        return False
    day_start = datetime.combine(day, time.min, zone)
    day_end = day_start + timedelta(days=1)
    return timing.starts_at < day_end and timing.ends_at > day_start


def _deduplicate_scoped(
    values: tuple[ScopedCalendarOccurrence, ...],
) -> tuple[ScopedCalendarOccurrence, ...]:
    units = {
        (item.occurrence.series_event_id, item.occurrence.occurrence_key): item.unit_id
        for item in values
    }
    occurrences = deduplicate_occurrences(tuple(item.occurrence for item in values))
    return tuple(
        ScopedCalendarOccurrence(
            units[(item.series_event_id, item.occurrence_key)],
            item,
        )
        for item in occurrences
    )
