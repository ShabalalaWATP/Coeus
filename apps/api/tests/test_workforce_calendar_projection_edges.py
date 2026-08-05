"""Boundary cases for calendar aggregation and bounded projection pages."""

from dataclasses import replace
from datetime import date, timedelta
from uuid import uuid4

from coeus.domain.organisation import MembershipState
from coeus.domain.workforce_calendar import CalendarTiming
from test_workforce_calendar_projection import NOW, setup


def test_incomplete_descendant_page_suppresses_aggregate_values() -> None:
    service, actor_id, root, _ = setup(member_total=5)
    base_events = service._projection._store.events  # type: ignore[attr-defined]
    # Deduplication is semantic, so each clone needs its own interval to count
    # as a distinct commitment rather than collapsing onto the seeded five.
    service._projection._store.events = tuple(
        replace(
            base_events[index % len(base_events)],
            event=replace(
                base_events[index % len(base_events)].event,
                event_id=uuid4(),
                timing=CalendarTiming(
                    "Europe/London",
                    starts_at=NOW + timedelta(days=1, minutes=index),
                    ends_at=NOW + timedelta(days=1, minutes=index + 30),
                ),
            ),
        )
        for index in range(101)
    )
    projection = service.team_projection(
        actor_id,
        root.unit_id,
        NOW,
        NOW + timedelta(days=7),
        include_descendants=True,
    )
    assert projection.truncated and projection.suppressed
    assert all(cell.unavailable_count is None for cell in projection.aggregates)


def test_descendant_timed_events_are_bucketed_and_inactive_members_are_excluded() -> None:
    service, actor_id, root, _ = setup(member_total=5)
    store = service._projection._store  # type: ignore[attr-defined]
    store.events = tuple(  # type: ignore[attr-defined]
        replace(
            item,
            event=replace(
                item.event,
                timing=CalendarTiming(
                    "Europe/London",
                    starts_at=NOW + timedelta(days=2),
                    ends_at=NOW + timedelta(days=2, hours=1),
                ),
            ),
        )
        for item in store.events  # type: ignore[attr-defined]
    )
    projection = service.team_projection(
        actor_id,
        root.unit_id,
        NOW,
        NOW + timedelta(days=7),
        include_descendants=True,
    )
    cell = next(item for item in projection.aggregates if item.day == date(2026, 8, 5))
    assert cell.unavailable_count == 5

    memberships = service._organisation.memberships  # type: ignore[attr-defined]
    service._organisation.memberships = (  # type: ignore[attr-defined]
        replace(memberships[0], state=MembershipState.SUSPENDED, assignment_eligible=False),
        *memberships[1:],
    )
    first_user = service._users.users[memberships[1].user_id]  # type: ignore[attr-defined]
    first_user.is_active = False
    projection = service.team_projection(
        actor_id,
        root.unit_id,
        NOW,
        NOW + timedelta(days=7),
        include_descendants=True,
    )
    assert projection.member_count is None and projection.suppressed
