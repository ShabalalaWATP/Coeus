"""Authorisation and preview boundary for canonical workforce calendars."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from coeus.application.ports.access import UserLookup
from coeus.application.ports.organisation import OrganisationReader
from coeus.application.ports.workforce_calendar import WorkforceCalendarStore
from coeus.domain.calendar_commitments import CalendarCommitment, CalendarCommitmentResponse
from coeus.domain.calendar_deduplication import deduplicate_occurrences
from coeus.domain.calendar_mutation_hash import calendar_preview_hash
from coeus.domain.calendar_occurrence_policy import (
    OCCURRENCE_OPERATIONS,
    validate_occurrence_request,
)
from coeus.domain.calendar_recurrence import expand_event
from coeus.domain.organisation import ManagementAction
from coeus.domain.workforce_calendar import (
    CalendarEvent,
    CalendarEventSource,
    CalendarEventStatus,
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationDenied,
    CalendarMutationOperation,
    CalendarMutationPreview,
    CalendarMutationRequest,
    CalendarMutationResult,
    CalendarOccurrence,
    CalendarProjection,
    CalendarRecurrenceIntegrityError,
)
from coeus.services.organisation_authority import OrganisationScopeEvaluator
from coeus.services.workforce_authority import (
    PROCESS_WORKFORCE_AUTHORITY,
    WorkforceAuthority,
)
from coeus.services.workforce_calendar_projection import WorkforceCalendarProjectionService


class WorkforceCalendarService:
    def __init__(
        self,
        organisation: OrganisationReader,
        users: UserLookup,
        store: WorkforceCalendarStore,
        *,
        clock: Callable[[], datetime] | None = None,
        workforce_authority: WorkforceAuthority = PROCESS_WORKFORCE_AUTHORITY,
    ) -> None:
        self._organisation = organisation
        self._users = users
        self._store = store
        self._scope = OrganisationScopeEvaluator(organisation)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._workforce_authority = workforce_authority
        self._projection = WorkforceCalendarProjectionService(
            organisation, users, store, clock=self._clock
        )

    def personal_calendar(
        self, actor_user_id: UUID, window_start: datetime, window_end: datetime
    ) -> tuple[CalendarOccurrence, ...]:
        if window_end <= window_start:
            raise ValueError("calendar window end must follow its start")
        if window_end - window_start > timedelta(days=366):
            raise ValueError("personal calendar window cannot exceed 366 days")
        seeds = self._store.list_owner_events(actor_user_id, window_start, window_end)
        try:
            occurrences = deduplicate_occurrences(
                tuple(
                    occurrence
                    for seed in seeds
                    for occurrence in expand_event(seed, window_start, window_end)
                )
            )
        except ValueError as exc:
            raise CalendarRecurrenceIntegrityError(
                "stored calendar recurrence cannot be expanded"
            ) from exc
        return tuple(
            sorted(
                occurrences,
                key=lambda item: (
                    item.event.timing.starts_at
                    or datetime.combine(
                        item.event.timing.all_day_start or date.min,
                        datetime.min.time(),
                        UTC,
                    ),
                ),
            )[:100]
        )

    def team_projection(
        self,
        actor_user_id: UUID,
        root_unit_id: UUID,
        window_start: datetime,
        window_end: datetime,
        *,
        include_descendants: bool = False,
        request_detail: bool = False,
    ) -> CalendarProjection:
        return self._projection.project(
            actor_user_id,
            root_unit_id,
            window_start,
            window_end,
            include_descendants=include_descendants,
            request_detail=request_detail,
        )

    def commitments(self, actor_user_id: UUID) -> tuple[CalendarCommitment, ...]:
        self._require_active_user(actor_user_id)
        return self._store.list_commitments(actor_user_id)

    def respond_to_commitment(
        self, actor_user_id: UUID, response: CalendarCommitmentResponse
    ) -> CalendarCommitment:
        self._require_active_user(actor_user_id)
        if response.subject_user_id != actor_user_id:
            raise CalendarMutationDenied("commitments can only be answered by their subject")
        return self._store.respond_commitment(response)

    def preview(
        self, request: CalendarMutationRequest, actor_user_id: UUID
    ) -> CalendarMutationPreview:
        now = self._clock()
        self._require_active_user(request.event.owner_user_id)
        existing = self._existing(request)
        self._validate_source(request, existing, actor_user_id, now)
        self._validate_lifecycle(request, existing, actor_user_id)
        if existing is not None:
            validate_occurrence_request(request, existing)
        if (
            request.future_event_id is not None
            and self._store.get_event(request.future_event_id) is not None
        ):
            raise CalendarMutationConflict("the future calendar series already exists")
        self._validate_window(request.event, now)
        snapshot = self._store.inspect(request)
        if snapshot.current_version != request.expected_version:
            raise CalendarMutationConflict("the calendar event version is stale")
        return CalendarMutationPreview(
            request,
            snapshot,
            calendar_preview_hash(request, actor_user_id, snapshot),
        )

    def execute(self, command: CalendarMutationCommand) -> CalendarMutationResult:
        with self._workforce_authority.locked():
            replay = self._store.replay(command)
            if replay is not None:
                return replay
            preview = self.preview(command.request, command.actor_user_id)
            if preview.preview_hash != command.preview_hash:
                raise CalendarMutationConflict("the calendar preview is stale")
            return self._store.apply(command)

    def _existing(self, request: CalendarMutationRequest) -> CalendarEvent | None:
        existing = self._store.get_event(request.event.event_id)
        if request.operation is CalendarMutationOperation.CREATE:
            if existing is not None:
                raise CalendarMutationConflict("the calendar event already exists")
            return None
        if existing is None:
            raise CalendarMutationConflict("the calendar event does not exist")
        return existing

    def _validate_source(
        self,
        request: CalendarMutationRequest,
        existing: CalendarEvent | None,
        actor_user_id: UUID,
        now: datetime,
    ) -> None:
        event = request.event
        if event.source is CalendarEventSource.PERSONAL:
            if actor_user_id != event.owner_user_id or request.authorising_grant_id is not None:
                raise CalendarMutationDenied("personal events are owner-managed")
            return
        if event.source not in {CalendarEventSource.MANAGER, CalendarEventSource.TEAM}:
            raise CalendarMutationDenied("this event source has a separate authority path")
        target_unit_id: UUID | None
        if event.source is CalendarEventSource.MANAGER:
            membership = self._organisation.effective_membership(event.owner_user_id, now)
            if membership is None or event.manager_scope_unit_id != membership.unit_id:
                raise CalendarMutationConflict("the subject has no matching current home unit")
            target_unit_id = membership.unit_id
        else:
            target_unit_id = event.manager_scope_unit_id
            unit = None if target_unit_id is None else self._organisation.get_unit(target_unit_id)
            if unit is None or not unit.is_active:
                raise CalendarMutationConflict("the team calendar scope is not active")
        if target_unit_id is None:
            raise CalendarMutationConflict("the calendar scope is unavailable")
        grant_id = request.authorising_grant_id
        decision = self._scope.evaluate(
            actor_user_id,
            target_unit_id,
            ManagementAction.CALENDAR_MANAGE,
            now,
            required_grant_id=grant_id,
        )
        if grant_id is None or not decision.allowed:
            raise CalendarMutationDenied("no effective calendar management grant")
        if existing is not None and existing.source not in {
            CalendarEventSource.MANAGER,
            CalendarEventSource.TEAM,
        }:
            raise CalendarMutationDenied("managers cannot change personal events")

    @staticmethod
    def _validate_lifecycle(
        request: CalendarMutationRequest,
        existing: CalendarEvent | None,
        actor_user_id: UUID,
    ) -> None:
        event = request.event
        if request.operation is CalendarMutationOperation.CREATE:
            if (
                event.version != 1
                or event.status is not CalendarEventStatus.ACTIVE
                or event.created_by_user_id != actor_user_id
            ):
                raise CalendarMutationConflict("new calendar event metadata is invalid")
            return
        if existing is None:
            raise CalendarMutationConflict("the calendar event does not exist")
        immutable = (
            event.event_id,
            event.owner_user_id,
            event.source,
            event.created_by_user_id,
            event.manager_scope_unit_id,
        )
        current = (
            existing.event_id,
            existing.owner_user_id,
            existing.source,
            existing.created_by_user_id,
            existing.manager_scope_unit_id,
        )
        if immutable != current or event.version != request.expected_version:
            raise CalendarMutationConflict("immutable calendar identity changed")
        if request.operation in {
            CalendarMutationOperation.UPDATE,
            CalendarMutationOperation.UPDATE_OCCURRENCE,
            CalendarMutationOperation.UPDATE_FUTURE,
        }:
            if event.status is not CalendarEventStatus.ACTIVE:
                raise CalendarMutationConflict("updates require an active event")
        elif existing.status is not CalendarEventStatus.ACTIVE:
            raise CalendarMutationConflict("only active events can be cancelled")
        if request.operation not in OCCURRENCE_OPERATIONS and event.exceptions:
            raise CalendarMutationConflict("calendar exceptions are server-managed")

    @staticmethod
    def _validate_window(event: CalendarEvent, now: datetime) -> None:
        timing = event.timing
        end = timing.ends_at
        recurrence_end = event.recurrence.until if event.recurrence is not None else None
        if (
            end is not None
            and end <= now
            and (recurrence_end is None or recurrence_end < now.date())
        ):
            raise CalendarMutationConflict("calendar events must end in the future")
        if (
            timing.all_day_end is not None
            and timing.all_day_end <= now.date()
            and (recurrence_end is None or recurrence_end < now.date())
        ):
            raise CalendarMutationConflict("calendar events must end in the future")

    def _require_active_user(self, user_id: UUID) -> None:
        user = self._users.get_user(user_id)
        if user is None or not user.is_active:
            raise CalendarMutationConflict("the calendar owner account is not active")
