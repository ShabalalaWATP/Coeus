"""Canonical team commitment and cross-source calendar policy tests."""

from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from coeus.domain.calendar_commitments import (
    CalendarCommitment,
    CalendarCommitmentResponse,
    CommitmentResponseState,
)
from coeus.domain.calendar_deduplication import deduplicate_occurrences
from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationManagementGrant,
    TeamMembership,
)
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarDeduplicationIntegrityError,
    CalendarEvent,
    CalendarEventSource,
    CalendarMutationConflict,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarMutationSnapshot,
    CalendarOccurrence,
    CalendarPrivacy,
    CalendarTiming,
)
from coeus.services.workforce_calendar import WorkforceCalendarService

NOW = datetime(2026, 8, 4, 9, tzinfo=UTC)


def _event(source: CalendarEventSource, *, key: str | None = None) -> CalendarEvent:
    owner, creator, unit = uuid4(), uuid4(), uuid4()
    return CalendarEvent(
        uuid4(),
        owner,
        source,
        CalendarActivity.TRAINING,
        CalendarTiming(
            "Europe/London",
            all_day_start=date(2026, 8, 10),
            all_day_end=date(2026, 8, 11),
        ),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.TEAM_SUMMARY,
        creator,
        "Synthetic exercise",
        manager_scope_unit_id=(
            unit if source in {CalendarEventSource.MANAGER, CalendarEventSource.TEAM} else None
        ),
        deduplication_key=key,
    )


def _occurrence(event: CalendarEvent) -> CalendarOccurrence:
    return CalendarOccurrence(event.event_id, "single", event)


def test_exact_overlap_deduplicates_by_precedence_and_restores_lower_source() -> None:
    personal = _event(CalendarEventSource.PERSONAL)
    manager = replace(
        _event(CalendarEventSource.MANAGER),
        owner_user_id=personal.owner_user_id,
        timing=personal.timing,
        activity=personal.activity,
        availability=personal.availability,
        deduplication_key=None,
    )
    task = replace(
        _event(CalendarEventSource.TASK),
        owner_user_id=personal.owner_user_id,
        timing=personal.timing,
        activity=personal.activity,
        availability=personal.availability,
    )
    chosen = deduplicate_occurrences(
        (_occurrence(personal), _occurrence(manager), _occurrence(task))
    )
    assert len(chosen) == 1
    assert chosen[0].event.source is CalendarEventSource.TASK
    assert chosen[0].duplicate_sources == (
        CalendarEventSource.TASK,
        CalendarEventSource.MANAGER,
        CalendarEventSource.PERSONAL,
    )
    restored = deduplicate_occurrences((_occurrence(personal), _occurrence(manager)))
    assert restored[0].event.source is CalendarEventSource.MANAGER


def test_explicit_identity_requires_matching_semantics_and_legacy_conflict_is_unknown() -> None:
    first = _event(CalendarEventSource.EXTERNAL, key="provider:item-1")
    moved = replace(
        first, event_id=uuid4(), timing=replace(first.timing, all_day_end=date(2026, 8, 12))
    )
    assert len(deduplicate_occurrences((_occurrence(first), _occurrence(moved)))) == 2
    legacy = replace(first, event_id=uuid4(), source=CalendarEventSource.LEGACY)
    conflict = replace(
        legacy,
        event_id=uuid4(),
        activity=CalendarActivity.LEAVE,
        deduplication_key="provider:item-2",
    )
    with pytest.raises(CalendarDeduplicationIntegrityError):
        deduplicate_occurrences((_occurrence(legacy), _occurrence(conflict)))


def test_commitment_response_contracts_require_subject_action_and_dispute_reason() -> None:
    manager = _event(CalendarEventSource.MANAGER)
    commitment = CalendarCommitment(manager, CommitmentResponseState.PENDING, 1, NOW)
    assert commitment.response_state is CommitmentResponseState.PENDING
    with pytest.raises(ValueError, match="manager events"):
        CalendarCommitment(
            _event(CalendarEventSource.PERSONAL), CommitmentResponseState.PENDING, 1, NOW
        )
    with pytest.raises(ValueError, match="pending"):
        CalendarCommitmentResponse(
            manager.event_id,
            manager.owner_user_id,
            CommitmentResponseState.PENDING,
            1,
        )
    with pytest.raises(ValueError, match="reason"):
        CalendarCommitmentResponse(
            manager.event_id,
            manager.owner_user_id,
            CommitmentResponseState.DISPUTED,
            1,
        )


class _User:
    def __init__(self, user_id):  # type: ignore[no-untyped-def]
        self.user_id, self.is_active = user_id, True


class _Users:
    def __init__(self, *ids):  # type: ignore[no-untyped-def]
        self.values = {value: _User(value) for value in ids}

    def get_user(self, user_id):  # type: ignore[no-untyped-def]
        return self.values.get(user_id)


class _Organisation:
    def __init__(self, membership, grant):  # type: ignore[no-untyped-def]
        self.membership, self.grant = membership, grant

    def effective_membership(self, user_id, effective_at):  # type: ignore[no-untyped-def]
        return self.membership if user_id == self.membership.user_id else None

    def effective_grants(self, manager_user_id, effective_at):  # type: ignore[no-untyped-def]
        return (self.grant,) if manager_user_id == self.grant.manager_user_id else ()

    def get_management_grant(self, grant_id):  # type: ignore[no-untyped-def]
        return self.grant if grant_id == self.grant.grant_id else None

    def unit_is_within(self, root, target):  # type: ignore[no-untyped-def]
        return root == target

    def get_unit(self, unit_id):  # type: ignore[no-untyped-def]
        class Unit:
            is_active = True

        return Unit() if unit_id == self.membership.unit_id else None


class _Store:
    def __init__(self, current=None):  # type: ignore[no-untyped-def]
        self.current = current

    def get_event(self, event_id):  # type: ignore[no-untyped-def]
        return self.current if self.current and self.current.event_id == event_id else None

    def inspect(self, request):  # type: ignore[no-untyped-def]
        return CalendarMutationSnapshot(0 if self.current is None else 1, 0, "a" * 64)


def _team_fixture():  # type: ignore[no-untyped-def]
    actor, subject, unit_id = uuid4(), uuid4(), uuid4()
    membership = TeamMembership(
        uuid4(),
        subject,
        unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        actor,
        "Synthetic posting",
        "test",
    )
    grant = OrganisationManagementGrant(
        uuid4(),
        actor,
        unit_id,
        ManagementAction.CALENDAR_MANAGE,
        False,
        NOW,
        actor,
        "Manage the exact team calendar",
    )
    event = replace(
        _event(CalendarEventSource.TEAM),
        owner_user_id=subject,
        created_by_user_id=actor,
        manager_scope_unit_id=unit_id,
    )
    return actor, subject, unit_id, membership, grant, event


def test_team_crud_requires_exact_calendar_manage_and_allows_authorised_successor() -> None:
    actor, subject, _unit_id, membership, grant, event = _team_fixture()
    organisation = _Organisation(membership, grant)
    create = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, event, 0, grant.grant_id, "Create team event."
    )
    service = WorkforceCalendarService(
        organisation, _Users(actor, subject), _Store(), clock=lambda: NOW
    )  # type: ignore[arg-type]
    assert service.preview(create, actor).request.event.source is CalendarEventSource.TEAM
    unrelated = replace(event, manager_scope_unit_id=uuid4())
    with pytest.raises(CalendarMutationConflict, match="scope is not active"):
        service.preview(replace(create, event=unrelated), actor)
    successor = uuid4()
    successor_grant = replace(grant, grant_id=uuid4(), manager_user_id=successor)
    update = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE,
        event,
        1,
        successor_grant.grant_id,
        "Successor updates team event.",
    )
    successor_service = WorkforceCalendarService(
        _Organisation(membership, successor_grant),
        _Users(successor, subject),
        _Store(event),
        clock=lambda: NOW,
    )  # type: ignore[arg-type]
    assert successor_service.preview(update, successor).snapshot.current_version == 1
