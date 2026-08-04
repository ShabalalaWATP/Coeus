"""Real PostgreSQL evidence for canonical team and manager commitments."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text

from coeus.domain.auth import UserAccount
from coeus.domain.calendar_commitments import (
    CalendarCommitmentResponse,
    CommitmentResponseState,
)
from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationTopologyRevision,
    OrganisationUnit,
    TeamMembership,
)
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarFrequency,
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationDenied,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.workforce_calendar_postgres import PostgresWorkforceCalendarStore
from coeus.services.workforce_calendar import WorkforceCalendarService

pytestmark = pytest.mark.postgres
API_ROOT = Path(__file__).resolve().parents[2]


class _Users:
    def __init__(self, *users: UserAccount) -> None:
        self.users = {item.user_id: item for item in users}

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self.users.get(user_id)


def _user(user_id: UUID, name: str) -> UserAccount:
    return UserAccount(user_id, name, name, frozenset(), frozenset(), "x", True, 1)


def _execute(
    service: WorkforceCalendarService,
    actor: UUID,
    request: CalendarMutationRequest,
    key: str,
):
    preview = service.preview(request, actor)
    return service.execute(
        CalendarMutationCommand(uuid4(), key, actor, request, preview.preview_hash)
    )


def test_team_crud_successor_response_races_and_notifications(
    postgres_database_url: str,
) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    organisation = PostgresOrganisationRepository(engine)
    now = datetime.now(UTC)
    manager_id, successor_id, subject_id = uuid4(), uuid4(), uuid4()
    activate_principals(engine, manager_id, successor_id)
    unit = OrganisationUnit(
        uuid4(),
        "Synthetic Calendar Team",
        "SYN-CAL",
        OrganisationCategory.DELIVERY_TEAM,
        None,
        now - timedelta(days=1),
    )
    organisation.upsert_unit(
        unit,
        OrganisationTopologyRevision(
            uuid4(), unit.unit_id, None, (unit.unit_id,), unit.valid_from, uuid4(), manager_id
        ),
    )
    unrelated_unit = replace(
        unit,
        unit_id=uuid4(),
        name="Unrelated Synthetic Team",
        short_name="SYN-OTHER",
    )
    organisation.upsert_unit(
        unrelated_unit,
        OrganisationTopologyRevision(
            uuid4(),
            unrelated_unit.unit_id,
            None,
            (unrelated_unit.unit_id,),
            unrelated_unit.valid_from,
            uuid4(),
            manager_id,
        ),
    )
    organisation.upsert_membership(
        TeamMembership(
            uuid4(),
            subject_id,
            unit.unit_id,
            MembershipRole.MEMBER,
            MembershipState.ACTIVE,
            True,
            now - timedelta(days=1),
            manager_id,
            "Synthetic posting.",
            "test",
        )
    )
    manage, successor_manage, view = (
        OrganisationManagementGrant(
            uuid4(),
            actor,
            unit.unit_id,
            action,
            False,
            now - timedelta(days=1),
            manager_id,
            "Synthetic exact calendar authority.",
        )
        for actor, action in (
            (manager_id, ManagementAction.CALENDAR_MANAGE),
            (successor_id, ManagementAction.CALENDAR_MANAGE),
            (manager_id, ManagementAction.CALENDAR_VIEW_DETAIL),
        )
    )
    for grant in (manage, successor_manage, view):
        organisation.upsert_management_grant(grant)
    store = PostgresWorkforceCalendarStore(engine)
    service = WorkforceCalendarService(
        organisation,
        _Users(
            _user(manager_id, "manager"),
            _user(successor_id, "successor"),
            _user(subject_id, "subject"),
        ),
        store,
        clock=lambda: now,
    )
    commitment = CalendarEvent(
        uuid4(),
        subject_id,
        CalendarEventSource.MANAGER,
        CalendarActivity.DUTY,
        CalendarTiming("Europe/London", now + timedelta(days=2), now + timedelta(days=2, hours=2)),
        AvailabilityEffect.PARTIAL,
        CalendarPrivacy.TEAM_SUMMARY,
        manager_id,
        "Synthetic duty commitment.",
        manager_scope_unit_id=unit.unit_id,
    )
    created = _execute(
        service,
        manager_id,
        CalendarMutationRequest(
            CalendarMutationOperation.CREATE,
            commitment,
            0,
            manage.grant_id,
            "Create manager commitment.",
        ),
        "create-manager-commitment",
    )
    assert created.version == 1
    pending = service.commitments(subject_id)[0]
    assert pending.response_state is CommitmentResponseState.PENDING
    acknowledged = service.respond_to_commitment(
        subject_id,
        CalendarCommitmentResponse(
            commitment.event_id,
            subject_id,
            CommitmentResponseState.ACKNOWLEDGED,
            1,
        ),
    )
    assert acknowledged.response_version == 2
    successor_update = replace(commitment, note="Successor adjusted commitment.", version=1)
    _execute(
        service,
        successor_id,
        CalendarMutationRequest(
            CalendarMutationOperation.UPDATE,
            successor_update,
            1,
            successor_manage.grant_id,
            "Authorised successor adjustment.",
        ),
        "successor-update",
    )
    reset = service.commitments(subject_id)[0]
    assert reset.response_state is CommitmentResponseState.PENDING
    with pytest.raises(CalendarMutationConflict, match="version is stale"):
        service.respond_to_commitment(
            subject_id,
            CalendarCommitmentResponse(
                commitment.event_id,
                subject_id,
                CommitmentResponseState.DISPUTED,
                2,
                "Stale response must lose the race.",
            ),
        )
    disputed = service.respond_to_commitment(
        subject_id,
        CalendarCommitmentResponse(
            commitment.event_id,
            subject_id,
            CommitmentResponseState.DISPUTED,
            reset.response_version,
            "The adjusted timing conflicts with approved leave.",
        ),
    )
    assert disputed.response_state is CommitmentResponseState.DISPUTED
    team_event = replace(
        commitment,
        event_id=uuid4(),
        owner_user_id=manager_id,
        source=CalendarEventSource.TEAM,
        note="Whole-team synthetic meeting.",
        recurrence=CalendarRecurrence(CalendarFrequency.DAILY, 1, (now + timedelta(days=4)).date()),
    )
    _execute(
        service,
        manager_id,
        CalendarMutationRequest(
            CalendarMutationOperation.CREATE,
            team_event,
            0,
            manage.grant_id,
            "Create team-scoped event.",
        ),
        "create-team-event",
    )
    occurrence_key = (now + timedelta(days=2)).date().isoformat()
    occurrence_change = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE_OCCURRENCE,
        replace(team_event, note="One changed synthetic occurrence.", version=1),
        1,
        manage.grant_id,
        "Change one team occurrence.",
        occurrence_key,
    )
    first_preview = service.preview(occurrence_change, manager_id)
    second_preview = service.preview(occurrence_change, manager_id)
    service.execute(
        CalendarMutationCommand(
            uuid4(),
            "first-team-occurrence-change",
            manager_id,
            occurrence_change,
            first_preview.preview_hash,
        )
    )
    with pytest.raises(CalendarMutationConflict):
        service.execute(
            CalendarMutationCommand(
                uuid4(),
                "stale-team-occurrence-change",
                manager_id,
                occurrence_change,
                second_preview.preview_hash,
            )
        )
    projection = service.team_projection(
        manager_id, unit.unit_id, now, now + timedelta(days=7), request_detail=True
    )
    assert any(entry.event_id == team_event.event_id for entry in projection.entries)
    unrelated = replace(team_event, event_id=uuid4(), manager_scope_unit_id=unrelated_unit.unit_id)
    with pytest.raises(CalendarMutationDenied):
        service.preview(
            CalendarMutationRequest(
                CalendarMutationOperation.CREATE,
                unrelated,
                0,
                manage.grant_id,
                "Reject unrelated team.",
            ),
            manager_id,
        )
    with engine.connect() as connection:
        notifications = connection.execute(
            text("SELECT notification_type FROM calendar_commitment_notifications")
        ).scalars()
        assert {"created", "changed", "acknowledged", "disputed"} <= set(notifications)
    engine.dispose()
