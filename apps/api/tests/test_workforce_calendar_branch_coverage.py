"""Focused branch coverage for canonical calendar validation and policy."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.calendar_mutation_hash import _serialise
from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationUnit,
    TeamMembership,
)
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarEventStatus,
    CalendarFrequency,
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationDenied,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarMutationResult,
    CalendarMutationSnapshot,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)
from coeus.services.workforce_calendar import WorkforceCalendarService

NOW = datetime(2026, 8, 4, 10, tzinfo=UTC)


class _User:
    def __init__(self, user_id: UUID, active: bool = True) -> None:
        self.user_id, self.is_active = user_id, active


class _Users:
    def __init__(self, *users: _User) -> None:
        self._users = {user.user_id: user for user in users}

    def get_user(self, user_id: UUID) -> _User | None:
        return self._users.get(user_id)


class _Organisation:
    def __init__(
        self, membership: TeamMembership | None, grants: tuple[OrganisationManagementGrant, ...]
    ) -> None:
        self.membership, self.grants = membership, grants

    def effective_membership(self, user_id: UUID, effective_at: datetime) -> TeamMembership | None:
        del effective_at
        return self.membership if self.membership and self.membership.user_id == user_id else None

    def effective_grants(
        self, manager_user_id: UUID, effective_at: datetime
    ) -> tuple[OrganisationManagementGrant, ...]:
        del effective_at
        return tuple(grant for grant in self.grants if grant.manager_user_id == manager_user_id)

    def get_management_grant(self, grant_id: UUID) -> OrganisationManagementGrant | None:
        return next((grant for grant in self.grants if grant.grant_id == grant_id), None)

    @staticmethod
    def unit_is_within(root_unit_id: UUID, target_unit_id: UUID) -> bool:
        return root_unit_id == target_unit_id


class _Store:
    def __init__(
        self,
        current: CalendarEvent | None = None,
        *,
        replay: CalendarMutationResult | None = None,
        snapshot_version: int | None = None,
    ) -> None:
        self.current, self.replayed = current, replay
        self.snapshot_version = snapshot_version

    def get_event(self, event_id: UUID) -> CalendarEvent | None:
        return self.current if self.current and self.current.event_id == event_id else None

    def inspect(self, request: CalendarMutationRequest) -> CalendarMutationSnapshot:
        del request
        version = (
            self.snapshot_version
            if self.snapshot_version is not None
            else (0 if self.current is None else self.current.version)
        )
        return CalendarMutationSnapshot(version, 0, "a" * 64)

    def replay(self, command: CalendarMutationCommand) -> CalendarMutationResult | None:
        del command
        return self.replayed

    @staticmethod
    def apply(command: CalendarMutationCommand) -> CalendarMutationResult:
        return CalendarMutationResult(command.request.event.event_id, 1)

    def list_owner_events(
        self, owner_user_id: UUID, window_start: datetime, window_end: datetime
    ) -> tuple[CalendarEvent, ...]:
        del owner_user_id, window_start, window_end
        return () if self.current is None else (self.current,)


def _fixture(
    source: CalendarEventSource = CalendarEventSource.PERSONAL,
) -> tuple[UUID, UUID, OrganisationManagementGrant, CalendarEvent, TeamMembership]:
    actor_id, owner_id, unit_id = uuid4(), uuid4(), uuid4()
    unit = OrganisationUnit(
        unit_id, "Branch Team", "BR", OrganisationCategory.DELIVERY_TEAM, None, NOW
    )
    membership = TeamMembership(
        uuid4(),
        owner_id,
        unit.unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        actor_id,
        "Branch fixture.",
        "test",
    )
    grant = OrganisationManagementGrant(
        uuid4(),
        actor_id,
        unit.unit_id,
        ManagementAction.CALENDAR_MANAGE,
        False,
        NOW,
        actor_id,
        "Branch fixture.",
    )
    event = CalendarEvent(
        uuid4(),
        owner_id,
        source,
        CalendarActivity.LEAVE,
        CalendarTiming("UTC", all_day_start=date(2026, 8, 5), all_day_end=date(2026, 8, 6)),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.PRIVATE,
        owner_id if source is CalendarEventSource.PERSONAL else actor_id,
        manager_scope_unit_id=unit.unit_id if source is CalendarEventSource.MANAGER else None,
    )
    return actor_id, owner_id, grant, event, membership


@pytest.mark.parametrize("interval", (0, 53))
def test_recurrence_rejects_interval_bounds(interval: int) -> None:
    with pytest.raises(ValueError, match="between one and 52"):
        CalendarRecurrence(CalendarFrequency.DAILY, interval, date(2026, 8, 9))


@pytest.mark.parametrize("weekdays", ((1, 1), (-1,), (7,)))
def test_recurrence_rejects_invalid_weekdays(weekdays: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="unique values"):
        CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 8, 9), weekdays)


def test_recurrence_requires_weekday_and_valid_event_window() -> None:
    with pytest.raises(ValueError, match="at least one"):
        CalendarRecurrence(CalendarFrequency.WEEKLY, 1, date(2026, 8, 9))
    _, _, _, event, _ = _fixture()
    with pytest.raises(ValueError, match="before the first"):
        replace(
            event,
            recurrence=CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 8, 4)),
        )


def test_timing_rejects_unknown_incomplete_and_reverse_ranges() -> None:
    with pytest.raises(ValueError, match="not recognised"):
        CalendarTiming("Not/AZone", all_day_start=date(2026, 8, 5), all_day_end=date(2026, 8, 6))
    with pytest.raises(ValueError, match="follow starts_at"):
        CalendarTiming("UTC", starts_at=NOW, ends_at=NOW)
    with pytest.raises(ValueError, match="follow all_day_start"):
        CalendarTiming("UTC", all_day_start=date(2026, 8, 5), all_day_end=date(2026, 8, 5))


def test_event_and_command_contracts_reject_invalid_metadata() -> None:
    _, _, grant, event, _ = _fixture()
    with pytest.raises(ValueError, match="version must be positive"):
        replace(event, version=0)
    with pytest.raises(ValueError, match="only manager"):
        replace(event, manager_scope_unit_id=grant.root_unit_id)
    with pytest.raises(ValueError, match="cancellation timestamp"):
        replace(event, status=CalendarEventStatus.CANCELLED)
    request = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, event, 0, None, "Create fixture."
    )
    with pytest.raises(ValueError, match="positive"):
        replace(request, operation=CalendarMutationOperation.UPDATE, expected_version=0)
    with pytest.raises(ValueError, match="non-negative"):
        CalendarMutationSnapshot(-1, 0, "a" * 64)
    with pytest.raises(ValueError, match="lowercase"):
        CalendarMutationSnapshot(0, 0, "A" * 64)
    assert _serialise((uuid4(), date(2026, 8, 4)))


def test_personal_calendar_and_execution_cover_validation_branches() -> None:
    _, owner_id, _, event, membership = _fixture()
    organisation = _Organisation(membership, ())
    store = _Store(event)
    service = WorkforceCalendarService(
        organisation, _Users(_User(owner_id)), store, clock=lambda: NOW
    )  # type: ignore[arg-type]
    occurrences = service.personal_calendar(owner_id, NOW, NOW + timedelta(days=1))
    assert len(occurrences) == 1
    assert occurrences[0].event == event
    assert occurrences[0].series_event_id == event.event_id
    assert occurrences[0].occurrence_key == "single"
    with pytest.raises(ValueError, match="follow"):
        service.personal_calendar(owner_id, NOW, NOW)
    replay = CalendarMutationResult(event.event_id, 7, True)
    replay_service = WorkforceCalendarService(
        organisation, _Users(_User(owner_id)), _Store(event, replay=replay), clock=lambda: NOW
    )  # type: ignore[arg-type]
    update = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE, event, 1, None, "Update fixture."
    )
    command = CalendarMutationCommand(uuid4(), "branch-replay", owner_id, update, "b" * 64)
    assert replay_service.execute(command) is replay
    with pytest.raises(CalendarMutationConflict, match="preview is stale"):
        service.execute(command)
    with pytest.raises(CalendarMutationConflict, match="version is stale"):
        WorkforceCalendarService(
            organisation,
            _Users(_User(owner_id)),
            _Store(event, snapshot_version=2),
            clock=lambda: NOW,
        ).preview(update, owner_id)  # type: ignore[arg-type]


def test_existing_source_owner_and_home_validation_fail_closed() -> None:
    actor_id, owner_id, grant, personal, membership = _fixture()
    organisation = _Organisation(membership, (grant,))
    active_users = _Users(_User(owner_id))
    create = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, personal, 0, None, "Create fixture."
    )
    with pytest.raises(CalendarMutationConflict, match="already exists"):
        WorkforceCalendarService(
            organisation, active_users, _Store(personal), clock=lambda: NOW
        ).preview(create, owner_id)  # type: ignore[arg-type]
    update = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE, personal, 1, None, "Update fixture."
    )
    with pytest.raises(CalendarMutationConflict, match="does not exist"):
        WorkforceCalendarService(organisation, active_users, _Store(), clock=lambda: NOW).preview(
            update, owner_id
        )  # type: ignore[arg-type]
    with pytest.raises(CalendarMutationDenied, match="owner-managed"):
        WorkforceCalendarService(organisation, active_users, _Store(), clock=lambda: NOW).preview(
            create, actor_id
        )  # type: ignore[arg-type]
    task_event = replace(personal, source=CalendarEventSource.TASK)
    with pytest.raises(CalendarMutationDenied, match="separate authority"):
        WorkforceCalendarService(organisation, active_users, _Store(), clock=lambda: NOW).preview(
            replace(create, event=task_event), owner_id
        )  # type: ignore[arg-type]
    manager_event = replace(
        personal,
        source=CalendarEventSource.MANAGER,
        created_by_user_id=actor_id,
        manager_scope_unit_id=grant.root_unit_id,
    )
    manager_create = replace(create, event=manager_event, authorising_grant_id=grant.grant_id)
    with pytest.raises(CalendarMutationConflict, match="matching current home"):
        WorkforceCalendarService(
            _Organisation(None, (grant,)), active_users, _Store(), clock=lambda: NOW
        ).preview(manager_create, actor_id)  # type: ignore[arg-type]


def test_lifecycle_window_account_and_manager_protections_fail_closed() -> None:
    actor_id, owner_id, grant, event, membership = _fixture(CalendarEventSource.MANAGER)
    organisation = _Organisation(membership, (grant,))
    users = _Users(_User(owner_id))
    create = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, event, 0, grant.grant_id, "Create fixture."
    )
    service = WorkforceCalendarService(organisation, users, _Store(), clock=lambda: NOW)  # type: ignore[arg-type]
    with pytest.raises(CalendarMutationConflict, match="metadata"):
        service.preview(
            replace(create, event=replace(event, created_by_user_id=owner_id)), actor_id
        )
    with pytest.raises(CalendarMutationDenied, match="management grant"):
        service.preview(replace(create, authorising_grant_id=None), actor_id)
    personal = replace(
        event,
        source=CalendarEventSource.PERSONAL,
        created_by_user_id=owner_id,
        manager_scope_unit_id=None,
    )
    manager_update = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE, personal, 1, grant.grant_id, "Change fixture."
    )
    with pytest.raises(CalendarMutationDenied, match="personal events"):
        service._validate_source(create, personal, actor_id, NOW)
    with pytest.raises(CalendarMutationConflict, match="immutable"):
        WorkforceCalendarService._validate_lifecycle(
            replace(manager_update, event=replace(personal, owner_user_id=uuid4())),
            personal,
            actor_id,
        )
    cancelled = replace(personal, status=CalendarEventStatus.CANCELLED, cancelled_at=NOW)
    with pytest.raises(CalendarMutationConflict, match="active event"):
        WorkforceCalendarService._validate_lifecycle(
            replace(manager_update, event=cancelled), personal, actor_id
        )
    cancel = replace(manager_update, operation=CalendarMutationOperation.CANCEL)
    with pytest.raises(CalendarMutationConflict, match="only active"):
        WorkforceCalendarService._validate_lifecycle(cancel, cancelled, actor_id)
    with pytest.raises(CalendarMutationConflict, match="does not exist"):
        WorkforceCalendarService._validate_lifecycle(manager_update, None, actor_id)
    past = replace(
        personal,
        timing=CalendarTiming("UTC", starts_at=NOW - timedelta(hours=2), ends_at=NOW),
    )
    with pytest.raises(CalendarMutationConflict, match="future"):
        WorkforceCalendarService._validate_window(past, NOW)
    inactive_service = WorkforceCalendarService(
        organisation, _Users(_User(owner_id, False)), _Store(), clock=lambda: NOW
    )  # type: ignore[arg-type]
    with pytest.raises(CalendarMutationConflict, match="account is not active"):
        inactive_service.preview(create, actor_id)
