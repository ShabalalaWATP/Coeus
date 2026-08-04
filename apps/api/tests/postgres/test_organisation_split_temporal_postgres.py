"""Temporal PostgreSQL evidence for organisation split dispositions."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from organisation_merge_support import (
    create_unit,
    foundation,
    upgrade,
)
from organisation_split_support import split_plan, split_request
from sqlalchemy import text

from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationManagementGrant,
    TeamMembership,
)
from coeus.domain.organisation_merge import (
    MergeDispositionAction,
    MergeRecordKind,
)
from coeus.domain.organisation_split import OrganisationSplitCommand
from coeus.persistence.organisation_split_postgres import PostgresOrganisationSplitStore
from coeus.services.organisation_split import OrganisationSplitService

pytestmark = pytest.mark.postgres


def _membership(
    user_id: UUID,
    unit_id: UUID,
    actor_id: UUID,
    valid_from: datetime,
    valid_until: datetime,
) -> TeamMembership:
    return TeamMembership(
        uuid4(),
        user_id,
        unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        valid_from,
        actor_id,
        "Synthetic fixed-term posting.",
        "synthetic-test",
        valid_until,
    )


def test_split_preserves_fixed_terms_and_cancels_scheduled_records(
    postgres_database_url: str,
) -> None:
    upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = foundation(postgres_database_url)
    parent_id = create_unit(engine, repository, lifecycle, actor_id, root_id, "Temporal Parent")
    source_id = create_unit(engine, repository, lifecycle, actor_id, parent_id, "Temporal Source")
    now = datetime.now(UTC)
    current_end = now + timedelta(days=5)
    future_start = now + timedelta(days=2)
    future_end = now + timedelta(days=8)
    current = _membership(uuid4(), source_id, actor_id, now - timedelta(days=1), current_end)
    future_move = _membership(uuid4(), source_id, actor_id, future_start, future_end)
    future_end_record = _membership(uuid4(), source_id, actor_id, future_start, future_end)
    for membership in (current, future_move, future_end_record):
        repository.upsert_membership(membership)
    future_grant = OrganisationManagementGrant(
        uuid4(),
        uuid4(),
        source_id,
        ManagementAction.TASK_ASSIGN,
        False,
        future_start,
        actor_id,
        "Synthetic scheduled authority.",
    )
    repository.upsert_management_grant(future_grant)
    request = split_request(engine, repository, source_id, parent_id)
    store = PostgresOrganisationSplitStore(engine)
    service = OrganisationSplitService(repository, store)
    impact = service.assess(request, actor_id)
    plan = split_plan(request, impact, current.membership_id)
    dispositions = tuple(
        replace(
            item,
            action=MergeDispositionAction.MOVE,
            target_unit_id=request.successors[0].unit_id,
            replacement_id=uuid4(),
        )
        if item.kind is MergeRecordKind.MEMBERSHIP and item.record_id == future_move.membership_id
        else item
        for item in plan.dispositions
    )
    preview = service.preview(replace(plan, dispositions=dispositions), actor_id)
    command = OrganisationSplitCommand(
        uuid4(), "temporal-split", actor_id, preview.plan, preview.preview_hash
    )
    service.execute(command)
    with engine.connect() as connection:
        current_rows = _membership_rows(connection, current.user_id)
        future_move_rows = _membership_rows(connection, future_move.user_id)
        future_end_rows = _membership_rows(connection, future_end_record.user_id)
        revoked_at = connection.execute(
            text("SELECT revoked_at FROM team_management_grants WHERE grant_id=:id"),
            {"id": future_grant.grant_id},
        ).scalar_one()
    assert len(current_rows) == 2
    assert current_rows[0].state == "ended"
    assert current_rows[1].valid_until == current_end
    assert current_rows[1].valid_from == current_rows[0].valid_until
    assert len(future_move_rows) == 2
    assert future_move_rows[0].state == "cancelled"
    assert future_move_rows[0].valid_until is None
    assert future_move_rows[1].valid_from == future_start
    assert future_move_rows[1].valid_until == future_end
    assert len(future_end_rows) == 1
    assert future_end_rows[0].state == "cancelled"
    assert future_end_rows[0].valid_until is None
    assert revoked_at == future_start
    engine.dispose()


def _membership_rows(connection, user_id: UUID):  # type: ignore[no-untyped-def]
    return connection.execute(
        text(
            "SELECT membership_id,state,valid_from,valid_until,unit_id "
            "FROM team_memberships WHERE user_id=:user_id ORDER BY created_at,membership_id"
        ),
        {"user_id": user_id},
    ).all()
