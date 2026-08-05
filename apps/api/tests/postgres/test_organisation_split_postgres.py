"""Real PostgreSQL evidence for explicit-disposition organisation splits."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from organisation_merge_support import (
    create_unit,
    foundation,
    seed_dependencies,
    upgrade,
)
from organisation_split_support import split_plan, split_request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from coeus.domain.organisation import (
    MembershipRole,
    MembershipState,
    TeamMembership,
)
from coeus.domain.organisation_merge import (
    MergeRecordKind,
    MergeUnitVersion,
)
from coeus.domain.organisation_split import (
    OrganisationSplitCommand,
    OrganisationSplitConflict,
    OrganisationSplitIdempotencyConflict,
)
from coeus.persistence.organisation_split_postgres import PostgresOrganisationSplitStore
from coeus.services.organisation_split import OrganisationSplitService

pytestmark = pytest.mark.postgres


def test_split_moves_dependencies_and_preserves_history(postgres_database_url: str) -> None:
    upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = foundation(postgres_database_url)
    parent_id = create_unit(engine, repository, lifecycle, actor_id, root_id, "Split Parent")
    source_id = create_unit(engine, repository, lifecycle, actor_id, parent_id, "Split Source")
    child_id = create_unit(engine, repository, lifecycle, actor_id, source_id, "Split Child")
    grandchild_id = create_unit(
        engine, repository, lifecycle, actor_id, child_id, "Split Grandchild"
    )
    dependencies = seed_dependencies(engine, repository, actor_id, source_id, source_id, parent_id)
    (
        moved_user_id,
        ended_user_id,
        membership_id,
        profile_id,
        coverage_id,
        direct_grant_id,
        transfer_id,
        ownership,
    ) = dependencies
    request = split_request(engine, repository, source_id, parent_id)
    store = PostgresOrganisationSplitStore(engine)
    service = OrganisationSplitService(repository, store)
    impact = service.assess(request, actor_id)
    assert {item.kind for item in impact.records} == set(MergeRecordKind)
    preview = service.preview(split_plan(request, impact, membership_id), actor_id)
    command = OrganisationSplitCommand(
        uuid4(), "split-source", actor_id, preview.plan, preview.preview_hash
    )
    result = service.execute(command)
    assert result.source.expected_version == 2
    assert result.parent.expected_version == request.parent.expected_version + 1
    assert service.execute(command).replayed and store.apply(command).replayed
    first_id, second_id = (item.unit_id for item in request.successors)
    source = repository.get_unit(source_id)
    child = repository.get_unit(child_id)
    grandchild = repository.get_unit(grandchild_id)
    assert source is not None and not source.is_active
    assert child is not None and child.parent_unit_id == first_id
    assert grandchild is not None and grandchild.parent_unit_id == child_id
    assert repository.unit_is_within(first_id, grandchild_id)
    assert not repository.unit_is_within(source_id, child_id)
    memberships = repository.list_memberships(moved_user_id)
    assert len(memberships) == 2 and memberships[0].membership_id == membership_id
    assert memberships[0].state is MembershipState.ENDED
    assert memberships[1].unit_id == first_id and memberships[1].assignment_eligible
    ended = repository.list_memberships(ended_user_id)
    assert len(ended) == 1 and ended[0].state is MembershipState.ENDED
    with engine.connect() as connection:
        profile = connection.execute(
            text("SELECT unit_id,policy_version FROM team_delivery_profiles WHERE profile_id=:id"),
            {"id": profile_id},
        ).one()
        capability_version = connection.execute(
            text("SELECT policy_version FROM team_capability_coverage WHERE coverage_id=:id"),
            {"id": coverage_id},
        ).scalar_one()
        task = connection.execute(
            text("SELECT owning_unit_id,version FROM team_task_ownership WHERE ownership_id=:id"),
            {"id": ownership.ownership_id},
        ).one()
        history_counts = tuple(
            connection.execute(text(statement), {"id": identity}).scalar_one()
            for statement, identity in (
                (
                    "SELECT count(*) FROM team_task_ownership_history WHERE ownership_id=:id",
                    ownership.ownership_id,
                ),
                (
                    "SELECT count(*) FROM team_delivery_profile_history WHERE profile_id=:id",
                    profile_id,
                ),
                (
                    "SELECT count(*) FROM team_capability_coverage_history WHERE coverage_id=:id",
                    coverage_id,
                ),
            )
        )
        revoked_at = connection.execute(
            text("SELECT revoked_at FROM team_management_grants WHERE grant_id=:id"),
            {"id": direct_grant_id},
        ).scalar_one()
        transfer_status = connection.execute(
            text("SELECT status FROM organisation_personnel_transfers WHERE command_id=:id"),
            {"id": transfer_id},
        ).scalar_one()
        revisions = connection.execute(
            text(
                "SELECT count(*) FROM organisation_topology_revisions WHERE change_command_id=:id"
            ),
            {"id": command.command_id},
        ).scalar_one()
        audit = connection.execute(
            text(
                "SELECT metadata::text FROM coeus_audit_events "
                "WHERE event_type='organisation_unit_split'"
            )
        ).scalar_one()
    assert UUID(str(profile.unit_id)) == first_id and profile.policy_version == 2
    assert capability_version == 2
    assert UUID(str(task.owning_unit_id)) == second_id and task.version == 2
    assert history_counts == (1, 1, 1)
    assert revoked_at is not None and transfer_status == "cancelled"
    assert revisions == 4
    assert request.reason not in audit
    changed = replace(request, reason="A different synthetic split reason.")
    with pytest.raises(OrganisationSplitIdempotencyConflict):
        store.replay(replace(command, plan=replace(preview.plan, request=changed)))
    with engine.begin() as connection, pytest.raises(DBAPIError, match="immutable"):
        connection.execute(
            text("SELECT set_config('coeus.organisation_split_command',:id,true)"),
            {"id": str(command.command_id)},
        )
        connection.execute(
            text(
                "DELETE FROM organisation_unit_closure "
                "WHERE ancestor_unit_id=:a AND descendant_unit_id=:d"
            ),
            {"a": first_id, "d": child_id},
        )
    engine.dispose()


def test_split_rejects_stale_dependency_inventory(postgres_database_url: str) -> None:
    upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = foundation(postgres_database_url)
    parent_id = create_unit(engine, repository, lifecycle, actor_id, root_id, "Stale Parent")
    source_id = create_unit(engine, repository, lifecycle, actor_id, parent_id, "Stale Source")
    request = split_request(engine, repository, source_id, parent_id)
    store = PostgresOrganisationSplitStore(engine)
    service = OrganisationSplitService(repository, store)
    preview = service.preview(split_plan(request, service.assess(request, actor_id)), actor_id)
    repository.upsert_membership(
        TeamMembership(
            uuid4(),
            uuid4(),
            source_id,
            MembershipRole.MEMBER,
            MembershipState.ACTIVE,
            False,
            datetime.now(UTC) - timedelta(seconds=1),
            actor_id,
            "Late synthetic posting.",
            "synthetic-test",
        )
    )
    command = OrganisationSplitCommand(
        uuid4(), "stale-split", actor_id, preview.plan, preview.preview_hash
    )
    with pytest.raises(OrganisationSplitConflict, match="disposition"):
        store.apply(command)
    with pytest.raises(OrganisationSplitConflict, match="disposition"):
        service.execute(command)
    assert repository.get_unit(source_id).is_active  # type: ignore[union-attr]
    assert all(repository.get_unit(item.unit_id) is None for item in request.successors)
    engine.dispose()


def test_split_inspection_rejects_missing_or_conflicting_units(
    postgres_database_url: str,
) -> None:
    upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = foundation(postgres_database_url)
    parent_id = create_unit(engine, repository, lifecycle, actor_id, root_id, "Inspect Parent")
    source_id = create_unit(engine, repository, lifecycle, actor_id, parent_id, "Inspect Source")
    request = split_request(engine, repository, source_id, parent_id)
    store = PostgresOrganisationSplitStore(engine)
    with pytest.raises(OrganisationSplitConflict, match="unavailable"):
        store.inspect(replace(request, source=MergeUnitVersion(uuid4(), 1)))
    existing_id = create_unit(engine, repository, lifecycle, actor_id, parent_id, "Red Successor")
    with pytest.raises(OrganisationSplitConflict, match="already exists"):
        store.inspect(
            replace(
                request,
                successors=(
                    replace(request.successors[0], unit_id=existing_id),
                    request.successors[1],
                ),
            )
        )
    engine.dispose()
