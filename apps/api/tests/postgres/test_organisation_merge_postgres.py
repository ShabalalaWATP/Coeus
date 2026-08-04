"""Real PostgreSQL evidence for explicit-disposition organisation merges."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from organisation_merge_support import (
    create_unit,
    foundation,
    merge_plan,
    merge_request,
    seed_dependencies,
    upgrade,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from coeus.domain.organisation import MembershipRole, MembershipState, TeamMembership
from coeus.domain.organisation_merge import (
    MergeRecordKind,
    MergeUnitAuthority,
    MergeUnitVersion,
    OrganisationMergeCommand,
    OrganisationMergeConflict,
    OrganisationMergeIdempotencyConflict,
    OrganisationMergeRequest,
)
from coeus.persistence.organisation_merge_postgres import PostgresOrganisationMergeStore
from coeus.services.organisation_merge import OrganisationMergeService

pytestmark = pytest.mark.postgres


def test_merge_inspection_rejects_missing_units(postgres_database_url: str) -> None:
    upgrade(postgres_database_url)
    engine, _, _, _, _ = foundation(postgres_database_url)
    versions = tuple(MergeUnitVersion(uuid4(), 1) for _ in range(3))
    request = OrganisationMergeRequest(
        versions[:2],
        versions[2],
        tuple(MergeUnitAuthority(item.unit_id, uuid4()) for item in versions),
        "Inspect missing synthetic units.",
    )
    with pytest.raises(OrganisationMergeConflict, match="unavailable"):
        PostgresOrganisationMergeStore(engine).inspect(request)
    engine.dispose()


def test_merge_moves_named_dependencies_and_preserves_history(postgres_database_url: str) -> None:
    upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = foundation(postgres_database_url)
    sources = tuple(
        create_unit(engine, repository, lifecycle, actor_id, root_id, name)
        for name in ("Alpha Delivery", "Bravo Delivery")
    )
    successor_id = create_unit(
        engine, repository, lifecycle, actor_id, root_id, "Combined Delivery"
    )
    nested_child_id = create_unit(
        engine, repository, lifecycle, actor_id, sources[0], "Nested Delivery"
    )
    nested_grandchild_id = create_unit(
        engine, repository, lifecycle, actor_id, nested_child_id, "Nested Specialist"
    )
    (
        user_id,
        ended_user_id,
        membership_id,
        profile_id,
        coverage_id,
        direct_grant_id,
        transfer_id,
        ownership,
    ) = seed_dependencies(engine, repository, actor_id, *sources, successor_id)
    request = merge_request(engine, repository, sources, successor_id)
    store = PostgresOrganisationMergeStore(engine)
    service = OrganisationMergeService(repository, store)
    impact = service.assess(request, actor_id)
    assert {item.kind for item in impact.records} == {
        MergeRecordKind.CHILD_UNIT,
        MergeRecordKind.MEMBERSHIP,
        MergeRecordKind.GRANT,
        MergeRecordKind.DELIVERY_PROFILE,
        MergeRecordKind.CAPABILITY,
        MergeRecordKind.TASK,
        MergeRecordKind.PENDING_TRANSFER,
    }
    preview = service.preview(merge_plan(request, impact), actor_id)
    record = OrganisationMergeCommand(
        uuid4(), "merge-alpha-bravo", actor_id, preview.plan, preview.preview_hash
    )
    result = service.execute(record)
    assert result.successor_version == 2
    assert service.execute(record).replayed and store.apply(record).replayed
    assert all(not repository.get_unit(item).is_active for item in sources)  # type: ignore[union-attr]
    nested_child = repository.get_unit(nested_child_id)
    nested_grandchild = repository.get_unit(nested_grandchild_id)
    assert nested_child is not None and nested_child.parent_unit_id == successor_id
    assert nested_grandchild is not None and nested_grandchild.parent_unit_id == nested_child_id
    assert repository.unit_is_within(successor_id, nested_grandchild_id)
    assert not any(repository.unit_is_within(source_id, nested_child_id) for source_id in sources)
    memberships = repository.list_memberships(user_id)
    assert len(memberships) == 2
    assert memberships[0].membership_id == membership_id
    assert memberships[0].state is MembershipState.ENDED
    assert memberships[1].unit_id == successor_id and memberships[1].assignment_eligible
    ended_memberships = repository.list_memberships(ended_user_id)
    assert len(ended_memberships) == 1
    assert ended_memberships[0].state is MembershipState.ENDED
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
        history = connection.execute(
            text("SELECT count(*) FROM team_task_ownership_history WHERE ownership_id=:id"),
            {"id": ownership.ownership_id},
        ).scalar_one()
        profile_history = connection.execute(
            text("SELECT count(*) FROM team_delivery_profile_history WHERE profile_id=:id"),
            {"id": profile_id},
        ).scalar_one()
        capability_history = connection.execute(
            text("SELECT count(*) FROM team_capability_coverage_history WHERE coverage_id=:id"),
            {"id": coverage_id},
        ).scalar_one()
        revoked_at = connection.execute(
            text("SELECT revoked_at FROM team_management_grants WHERE grant_id=:id"),
            {"id": direct_grant_id},
        ).scalar_one()
        transfer_status = connection.execute(
            text("SELECT status FROM organisation_personnel_transfers WHERE command_id=:id"),
            {"id": transfer_id},
        ).scalar_one()
        audit = connection.execute(
            text(
                "SELECT metadata::text FROM coeus_audit_events "
                "WHERE event_type='organisation_units_merged'"
            )
        ).scalar_one()
        moved_revisions = connection.execute(
            text(
                "SELECT count(*) FROM organisation_topology_revisions "
                "WHERE change_command_id=:command_id AND unit_id IN (:child_id,:grandchild_id)"
            ),
            {
                "command_id": record.command_id,
                "child_id": nested_child_id,
                "grandchild_id": nested_grandchild_id,
            },
        ).scalar_one()
    assert UUID(str(profile.unit_id)) == successor_id and profile.policy_version == 2
    assert capability_version == 2
    assert UUID(str(task.owning_unit_id)) == successor_id and task.version == 2
    assert history == profile_history == capability_history == 1
    assert revoked_at is not None and transfer_status == "cancelled"
    assert moved_revisions == 2
    assert request.reason not in audit
    changed_request = replace(request, reason="A different synthetic merge reason.")
    changed_plan = replace(preview.plan, request=changed_request)
    with pytest.raises(OrganisationMergeIdempotencyConflict):
        store.replay(replace(record, plan=changed_plan))
    with engine.begin() as connection, pytest.raises(DBAPIError, match="immutable"):
        connection.execute(
            text("SELECT set_config('coeus.organisation_merge_command',:command_id,true)"),
            {"command_id": str(record.command_id)},
        )
        connection.execute(
            text(
                "DELETE FROM organisation_unit_closure "
                "WHERE ancestor_unit_id=:ancestor AND descendant_unit_id=:descendant"
            ),
            {"ancestor": successor_id, "descendant": nested_child_id},
        )
    engine.dispose()


def test_merge_rejects_stale_dependency_inventory(postgres_database_url: str) -> None:
    upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = foundation(postgres_database_url)
    sources = tuple(
        create_unit(engine, repository, lifecycle, actor_id, root_id, name)
        for name in ("Stale Alpha", "Stale Bravo")
    )
    successor_id = create_unit(engine, repository, lifecycle, actor_id, root_id, "Stale Successor")
    request = merge_request(engine, repository, sources, successor_id)
    store = PostgresOrganisationMergeStore(engine)
    service = OrganisationMergeService(repository, store)
    preview = service.preview(merge_plan(request, service.assess(request, actor_id)), actor_id)
    repository.upsert_membership(
        TeamMembership(
            uuid4(),
            uuid4(),
            sources[0],
            MembershipRole.MEMBER,
            MembershipState.ACTIVE,
            False,
            datetime.now(UTC) - timedelta(seconds=1),
            actor_id,
            "Late synthetic posting.",
            "synthetic-test",
        )
    )
    record = OrganisationMergeCommand(
        uuid4(), "stale-merge", actor_id, preview.plan, preview.preview_hash
    )
    with pytest.raises(OrganisationMergeConflict, match="disposition"):
        store.apply(record)
    with pytest.raises(OrganisationMergeConflict, match="disposition"):
        service.execute(record)
    assert all(repository.get_unit(item).is_active for item in sources)  # type: ignore[union-attr]
    engine.dispose()
