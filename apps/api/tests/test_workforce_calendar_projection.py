"""Privacy and descendant-scope policy for canonical calendar projections."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

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
    CalendarPrivacy,
    CalendarProjectionDenied,
    CalendarProjectionDetail,
    CalendarTiming,
    ScopedCalendarEvent,
)
from coeus.services.workforce_calendar import WorkforceCalendarService

NOW = datetime(2026, 8, 3, 10, tzinfo=UTC)


class User:
    def __init__(self, user_id: UUID, is_active: bool = True) -> None:
        self.user_id, self.is_active = user_id, is_active


class Users:
    def __init__(self, users: tuple[User, ...]) -> None:
        self.users = {user.user_id: user for user in users}

    def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)


class Organisation:
    def __init__(
        self,
        root: OrganisationUnit,
        child: OrganisationUnit,
        memberships: tuple[TeamMembership, ...],
        grants: tuple[OrganisationManagementGrant, ...],
    ) -> None:
        self.units = {root.unit_id: root, child.unit_id: child}
        self.root, self.child = root, child
        self.memberships, self.grants = memberships, grants

    def get_unit(self, unit_id: UUID) -> OrganisationUnit | None:
        return self.units.get(unit_id)

    def list_descendants(self, unit_id: UUID, **_kwargs: object) -> tuple[OrganisationUnit, ...]:
        return (self.child,) if unit_id == self.root.unit_id else ()

    def list_unit_memberships(self, unit_id: UUID, **_kwargs: object) -> tuple[TeamMembership, ...]:
        return tuple(item for item in self.memberships if item.unit_id == unit_id)

    def effective_grants(
        self, manager_user_id: UUID, _effective_at: datetime
    ) -> tuple[OrganisationManagementGrant, ...]:
        return tuple(item for item in self.grants if item.manager_user_id == manager_user_id)

    def get_management_grant(self, grant_id: UUID) -> OrganisationManagementGrant | None:
        return next((item for item in self.grants if item.grant_id == grant_id), None)

    def unit_is_within(self, root_unit_id: UUID, target_unit_id: UUID) -> bool:
        return root_unit_id == target_unit_id or (
            root_unit_id == self.root.unit_id and target_unit_id == self.child.unit_id
        )


class Store:
    def __init__(self, events: tuple[ScopedCalendarEvent, ...]) -> None:
        self.events = events

    def list_unit_events(self, *_args: object) -> tuple[ScopedCalendarEvent, ...]:
        return self.events


def membership(user_id: UUID, unit_id: UUID) -> TeamMembership:
    return TeamMembership(
        uuid4(),
        user_id,
        unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        uuid4(),
        "Synthetic posting.",
        "test",
    )


def grant(
    actor_id: UUID,
    root_id: UUID,
    action: ManagementAction,
    *,
    descendants: bool = True,
) -> OrganisationManagementGrant:
    return OrganisationManagementGrant(
        uuid4(),
        actor_id,
        root_id,
        action,
        descendants,
        NOW,
        actor_id,
        "Synthetic calendar view.",
    )


def event(owner_id: UUID, privacy: CalendarPrivacy, note: str = "Private note") -> CalendarEvent:
    return CalendarEvent(
        uuid4(),
        owner_id,
        CalendarEventSource.PERSONAL,
        CalendarActivity.TRAINING,
        CalendarTiming(
            "Europe/London", all_day_start=date(2026, 8, 5), all_day_end=date(2026, 8, 6)
        ),
        AvailabilityEffect.PARTIAL,
        privacy,
        owner_id,
        note,
    )


def setup(
    *, detail: bool = False, descendants: bool = True, member_total: int = 2
) -> tuple[WorkforceCalendarService, UUID, OrganisationUnit, OrganisationUnit]:
    actor_id = uuid4()
    root = OrganisationUnit(
        uuid4(), "Synthetic Command", "Command", OrganisationCategory.COMMAND, None, NOW
    )
    child = OrganisationUnit(
        uuid4(),
        "Synthetic Team",
        "Team",
        OrganisationCategory.DELIVERY_TEAM,
        root.unit_id,
        NOW,
    )
    owners = tuple(uuid4() for _ in range(member_total))
    memberships = tuple(membership(owner, child.unit_id) for owner in owners)
    grants = [
        grant(
            actor_id,
            root.unit_id,
            ManagementAction.CALENDAR_VIEW_AVAILABILITY,
            descendants=descendants,
        )
    ]
    if detail:
        grants.append(grant(actor_id, root.unit_id, ManagementAction.CALENDAR_VIEW_DETAIL))
    events = tuple(
        ScopedCalendarEvent(
            child.unit_id,
            event(owner, CalendarPrivacy.TEAM_DETAIL if index == 0 else CalendarPrivacy.PRIVATE),
        )
        for index, owner in enumerate(owners)
    )
    organisation = Organisation(root, child, memberships, tuple(grants))
    service = WorkforceCalendarService(
        organisation,
        Users((*tuple(User(owner) for owner in owners), User(actor_id))),
        Store(events),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    return service, actor_id, root, child


def test_direct_availability_projection_redacts_identity_activity_and_note() -> None:
    service, actor_id, _, child = setup()
    projection = service.team_projection(actor_id, child.unit_id, NOW, NOW + timedelta(days=7))
    assert projection.member_count == 2 and not projection.suppressed
    assert all(item.detail is CalendarProjectionDetail.AVAILABILITY for item in projection.entries)
    assert all(
        item.owner_user_id is None and item.activity is None and item.note is None
        for item in projection.entries
    )


def test_detail_authority_respects_each_event_privacy_level() -> None:
    service, actor_id, _, child = setup(detail=True)
    projection = service.team_projection(
        actor_id, child.unit_id, NOW, NOW + timedelta(days=7), request_detail=True
    )
    detailed, private = projection.entries
    assert detailed.owner_user_id is not None
    assert detailed.activity is CalendarActivity.TRAINING and detailed.note == "Private note"
    assert private.owner_user_id is not None
    assert private.activity is None and private.note is None


def test_descendant_projection_requires_descendant_grant_and_suppresses_small_cohort() -> None:
    service, actor_id, root, child = setup(descendants=False)
    with pytest.raises(CalendarProjectionDenied):
        service.team_projection(
            actor_id,
            root.unit_id,
            NOW,
            NOW + timedelta(days=7),
            include_descendants=True,
        )

    service, actor_id, root, child = setup()
    projection = service.team_projection(
        actor_id,
        root.unit_id,
        NOW,
        NOW + timedelta(days=7),
        include_descendants=True,
    )
    assert projection.suppressed and projection.member_count is None
    assert projection.entries == () and child.unit_id in projection.unit_ids


def test_descendant_projection_releases_bounded_availability_at_five_members() -> None:
    service, actor_id, root, _ = setup(member_total=5)
    projection = service.team_projection(
        actor_id,
        root.unit_id,
        NOW,
        NOW + timedelta(days=7),
        include_descendants=True,
    )
    assert not projection.suppressed and projection.member_count == 5
    assert projection.entries == ()
    august_fifth = next(cell for cell in projection.aggregates if cell.day == date(2026, 8, 5))
    assert august_fifth.member_count == 5
    assert august_fifth.unavailable_count == 5 and not august_fifth.suppressed


def test_projection_rejects_missing_authority_inactive_scope_and_oversized_window() -> None:
    service, actor_id, root, child = setup()
    service._organisation.grants = ()  # type: ignore[attr-defined]
    with pytest.raises(CalendarProjectionDenied):
        service.team_projection(actor_id, root.unit_id, NOW, NOW + timedelta(days=7))
    service._organisation.units[root.unit_id] = replace(root, is_active=False)  # type: ignore[attr-defined]
    with pytest.raises(CalendarProjectionDenied):
        service.team_projection(actor_id, root.unit_id, NOW, NOW + timedelta(days=7))
    service._organisation.units[root.unit_id] = root  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="92"):
        service.team_projection(actor_id, child.unit_id, NOW, NOW + timedelta(days=93))
    with pytest.raises(ValueError, match="31"):
        service.team_projection(
            actor_id,
            root.unit_id,
            NOW,
            NOW + timedelta(days=32),
            include_descendants=True,
        )
    with pytest.raises(ValueError, match="end must follow"):
        service.team_projection(actor_id, child.unit_id, NOW, NOW)


def test_detail_view_requires_explicit_detail_grant() -> None:
    service, actor_id, _, child = setup(detail=False)
    with pytest.raises(CalendarProjectionDenied):
        service.team_projection(
            actor_id,
            child.unit_id,
            NOW,
            NOW + timedelta(days=7),
            request_detail=True,
        )


def test_self_detail_preserves_exact_timing_while_availability_is_coarsened() -> None:
    service, actor_id, _, child = setup(detail=True)
    timed = event(actor_id, CalendarPrivacy.PRIVATE)
    timed = replace(
        timed,
        timing=CalendarTiming(
            "Europe/London",
            starts_at=NOW + timedelta(days=2, hours=1),
            ends_at=NOW + timedelta(days=2, hours=3),
        ),
    )
    service._organisation.memberships = (membership(actor_id, child.unit_id),)  # type: ignore[attr-defined]
    service._projection._store.events = (  # type: ignore[attr-defined]
        ScopedCalendarEvent(child.unit_id, timed),
    )

    availability = service.team_projection(actor_id, child.unit_id, NOW, NOW + timedelta(days=7))
    assert availability.entries[0].timing.all_day_start == date(2026, 8, 5)
    assert availability.entries[0].event_id is None

    detail = service.team_projection(
        actor_id,
        child.unit_id,
        NOW,
        NOW + timedelta(days=7),
        request_detail=True,
    )
    assert detail.entries[0].detail is CalendarProjectionDetail.SELF
    assert detail.entries[0].event_id == timed.event_id
    assert detail.entries[0].timing.starts_at == timed.timing.starts_at
