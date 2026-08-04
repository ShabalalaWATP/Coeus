"""Policy tests for canonical calendar personal and manager mutations."""

from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

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
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationDenied,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarMutationResult,
    CalendarMutationSnapshot,
    CalendarPrivacy,
    CalendarTiming,
)
from coeus.services.workforce_calendar import WorkforceCalendarService

NOW = datetime(2026, 8, 3, 10, tzinfo=UTC)


class User:
    def __init__(self, user_id, is_active=True):  # type: ignore[no-untyped-def]
        self.user_id, self.is_active = user_id, is_active


class Users:
    def __init__(self, *users):  # type: ignore[no-untyped-def]
        self.users = {user.user_id: user for user in users}

    def get_user(self, user_id):  # type: ignore[no-untyped-def]
        return self.users.get(user_id)


class Organisation:
    def __init__(self, unit, membership, grants=()):  # type: ignore[no-untyped-def]
        self.unit, self.membership, self.grants = unit, membership, grants

    def effective_membership(self, user_id, effective_at):  # type: ignore[no-untyped-def]
        return self.membership if user_id == self.membership.user_id else None

    def effective_grants(self, manager_user_id, effective_at):  # type: ignore[no-untyped-def]
        return tuple(grant for grant in self.grants if grant.manager_user_id == manager_user_id)

    def get_management_grant(self, grant_id):  # type: ignore[no-untyped-def]
        return next((grant for grant in self.grants if grant.grant_id == grant_id), None)

    def unit_is_within(self, root_unit_id, target_unit_id):  # type: ignore[no-untyped-def]
        return root_unit_id == target_unit_id


class Store:
    def __init__(self, current=None):  # type: ignore[no-untyped-def]
        self.current, self.command = current, None

    def get_event(self, event_id):  # type: ignore[no-untyped-def]
        return self.current if self.current and self.current.event_id == event_id else None

    def inspect(self, request):  # type: ignore[no-untyped-def]
        return CalendarMutationSnapshot(
            0 if self.current is None else self.current.version, 1, "a" * 64
        )

    def replay(self, command):  # type: ignore[no-untyped-def]
        return None

    def apply(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        return CalendarMutationResult(
            command.request.event.event_id, command.request.expected_version + 1
        )

    def list_owner_events(self, owner_user_id, starts_before, ends_after):  # type: ignore[no-untyped-def]
        return () if self.current is None else (self.current,)


def fixture(source=CalendarEventSource.PERSONAL):  # type: ignore[no-untyped-def]
    actor_id, owner_id, unit_id, grant_id = (uuid4() for _ in range(4))
    unit = OrganisationUnit(
        unit_id, "Synthetic Team", "Team", OrganisationCategory.DELIVERY_TEAM, None, NOW
    )
    membership = TeamMembership(
        uuid4(),
        owner_id,
        unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        actor_id,
        "Synthetic posting",
        "test",
    )
    grant = OrganisationManagementGrant(
        grant_id,
        actor_id,
        unit_id,
        ManagementAction.CALENDAR_MANAGE,
        True,
        NOW,
        actor_id,
        "Manage synthetic calendar",
    )
    creator = owner_id if source is CalendarEventSource.PERSONAL else actor_id
    event = CalendarEvent(
        uuid4(),
        owner_id,
        source,
        CalendarActivity.LEAVE,
        CalendarTiming(
            "Europe/London", all_day_start=date(2026, 8, 5), all_day_end=date(2026, 8, 6)
        ),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.PRIVATE,
        creator,
        manager_scope_unit_id=unit_id if source is CalendarEventSource.MANAGER else None,
    )
    return actor_id, owner_id, grant, event, Organisation(unit, membership, (grant,))


def test_owner_previews_and_executes_exact_personal_event() -> None:
    _, owner_id, _, event, organisation = fixture()
    store = Store()
    service = WorkforceCalendarService(
        organisation, Users(User(owner_id)), store, clock=lambda: NOW
    )  # type: ignore[arg-type]
    request = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, event, 0, None, "Create leave."
    )
    preview = service.preview(request, owner_id)
    result = service.execute(
        CalendarMutationCommand(uuid4(), "create-leave", owner_id, request, preview.preview_hash)
    )
    assert result.version == 1 and store.command is not None


def test_manager_requires_exact_calendar_grant_and_cannot_change_personal_event() -> None:
    actor_id, owner_id, grant, event, organisation = fixture(CalendarEventSource.MANAGER)
    service = WorkforceCalendarService(
        organisation, Users(User(owner_id)), Store(), clock=lambda: NOW
    )  # type: ignore[arg-type]
    request = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, event, 0, grant.grant_id, "Create duty."
    )
    assert service.preview(request, actor_id).snapshot.current_version == 0
    with pytest.raises(CalendarMutationDenied):
        service.preview(replace(request, authorising_grant_id=uuid4()), actor_id)
    personal = replace(
        event,
        source=CalendarEventSource.PERSONAL,
        manager_scope_unit_id=None,
        created_by_user_id=owner_id,
    )
    update = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE, personal, 1, grant.grant_id, "Change private event."
    )
    with pytest.raises(CalendarMutationDenied):
        WorkforceCalendarService(
            organisation, Users(User(owner_id)), Store(personal), clock=lambda: NOW
        ).preview(update, actor_id)  # type: ignore[arg-type]


def test_stale_and_past_events_fail_closed() -> None:
    _, owner_id, _, event, organisation = fixture()
    current = replace(event, version=2)
    service = WorkforceCalendarService(
        organisation, Users(User(owner_id)), Store(current), clock=lambda: NOW
    )  # type: ignore[arg-type]
    stale = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE, replace(event, version=1), 1, None, "Stale."
    )
    with pytest.raises(CalendarMutationConflict, match="version"):
        service.preview(stale, owner_id)
    past = replace(
        event,
        timing=CalendarTiming(
            "Europe/London", all_day_start=date(2026, 8, 1), all_day_end=date(2026, 8, 2)
        ),
    )
    service = WorkforceCalendarService(
        organisation, Users(User(owner_id)), Store(), clock=lambda: NOW
    )  # type: ignore[arg-type]
    with pytest.raises(CalendarMutationConflict, match="future"):
        service.preview(
            CalendarMutationRequest(CalendarMutationOperation.CREATE, past, 0, None, "Past."),
            owner_id,
        )
