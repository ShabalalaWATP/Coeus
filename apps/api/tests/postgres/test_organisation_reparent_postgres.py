"""Real PostgreSQL evidence for safe organisation reparenting."""

from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from coeus.domain.organisation import ManagementAction, OrganisationCategory
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
)
from coeus.domain.organisation_reparent import (
    OrganisationReparentCommand,
    OrganisationReparentConflict,
    OrganisationReparentIdempotencyConflict,
    OrganisationReparentRequest,
)
from coeus.persistence.organisation_bootstrap_postgres import (
    PostgresOrganisationBootstrapStore,
)
from coeus.persistence.organisation_lifecycle_postgres import (
    PostgresOrganisationMutationStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.organisation_reparent_postgres import (
    PostgresOrganisationReparentStore,
)
from coeus.services.organisation_lifecycle import OrganisationLifecycleService
from coeus.services.organisation_reparent import OrganisationReparentService

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _foundation(database_url: str):  # type: ignore[no-untyped-def]
    engine = create_engine(database_url)
    actor_id, root_id = uuid4(), uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(),
            actor_id,
            root_id,
            "Synthetic Defence Intelligence",
            "Synthetic DI",
            "Europe/London",
            "Synthetic hierarchy root.",
        )
    )
    activate_principals(engine, actor_id)
    repository = PostgresOrganisationRepository(engine)
    lifecycle = OrganisationLifecycleService(repository, PostgresOrganisationMutationStore(engine))
    return engine, repository, lifecycle, actor_id, root_id


def _grant_id(engine, action: ManagementAction) -> UUID:  # type: ignore[no-untyped-def]
    with engine.connect() as connection:
        return UUID(
            str(
                connection.execute(
                    text("SELECT grant_id FROM team_management_grants WHERE action=:action"),
                    {"action": action.value},
                ).scalar_one()
            )
        )


def _create_unit(  # type: ignore[no-untyped-def]
    lifecycle: OrganisationLifecycleService,
    repository: PostgresOrganisationRepository,
    engine,
    actor_id: UUID,
    parent_id: UUID,
    name: str,
):
    parent = repository.get_unit(parent_id)
    assert parent is not None
    unit_id = uuid4()
    request = OrganisationMutationRequest(
        OrganisationMutationOperation.CREATE,
        unit_id,
        parent_id,
        parent.version,
        name,
        name[:12],
        OrganisationCategory.BRANCH,
        "Europe/London",
        f"Synthetic {name} unit.",
        _grant_id(engine, ManagementAction.ORGANISATION_CREATE),
        f"Create synthetic {name}.",
    )
    preview = lifecycle.preview(request, actor_id)
    result = lifecycle.execute(
        OrganisationMutationCommand(
            uuid4(),
            f"create-{name.lower().replace(' ', '-')}",
            actor_id,
            request,
            preview.preview_hash,
        )
    )
    return unit_id, result.topology_revision_id


def _tree(database_url: str):  # type: ignore[no-untyped-def]
    engine, repository, lifecycle, actor_id, root_id = _foundation(database_url)
    source_parent_id, _ = _create_unit(
        lifecycle, repository, engine, actor_id, root_id, "Source Branch"
    )
    target_id, _ = _create_unit(lifecycle, repository, engine, actor_id, root_id, "Target Branch")
    moved_id, _ = _create_unit(
        lifecycle, repository, engine, actor_id, source_parent_id, "Moved Team"
    )
    child_id, _ = _create_unit(lifecycle, repository, engine, actor_id, moved_id, "Moved Subteam")
    return engine, repository, actor_id, source_parent_id, target_id, moved_id, child_id


def _request(engine, repository, moved_id: UUID, target_id: UUID):  # type: ignore[no-untyped-def]
    moved = repository.get_unit(moved_id)
    target = repository.get_unit(target_id)
    assert moved is not None and target is not None
    return OrganisationReparentRequest(
        moved_id,
        target_id,
        moved.version,
        target.version,
        _grant_id(engine, ManagementAction.ORGANISATION_REPARENT),
        "Move the synthetic subtree to its approved parent.",
    )


def test_reparent_moves_complete_subtree_and_preserves_evidence(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, repository, actor_id, old_parent_id, target_id, moved_id, child_id = _tree(
        postgres_database_url
    )
    store = PostgresOrganisationReparentStore(engine)
    service = OrganisationReparentService(repository, store)
    request = _request(engine, repository, moved_id, target_id)
    preview = service.preview(request, actor_id)
    assert preview.impact.descendants == 1
    assert preview.impact.maximum_result_depth == 3
    command_record = OrganisationReparentCommand(
        uuid4(), "move-subtree-to-target", actor_id, request, preview.preview_hash
    )
    result = service.execute(command_record)
    assert result.version == 2
    assert service.execute(command_record).replayed
    assert store.apply(command_record).replayed

    with engine.connect() as connection:
        moved_path = tuple(
            connection.execute(
                text(
                    "SELECT ancestor_unit_id FROM organisation_unit_closure "
                    "WHERE descendant_unit_id=:unit_id ORDER BY depth DESC"
                ),
                {"unit_id": moved_id},
            ).scalars()
        )
        child_path = tuple(
            connection.execute(
                text(
                    "SELECT ancestor_unit_id FROM organisation_unit_closure "
                    "WHERE descendant_unit_id=:unit_id ORDER BY depth DESC"
                ),
                {"unit_id": child_id},
            ).scalars()
        )
        revision_count = connection.execute(
            text(
                "SELECT count(*) FROM organisation_topology_revisions "
                "WHERE change_command_id=:command_id"
            ),
            {"command_id": command_record.command_id},
        ).scalar_one()
        evidence = connection.execute(
            text(
                "SELECT metadata::text FROM coeus_audit_events "
                "WHERE event_type='organisation_unit_reparented'"
            )
        ).scalar_one()
    assert target_id in moved_path and old_parent_id not in moved_path
    assert target_id in child_path and old_parent_id not in child_path
    assert revision_count == 2
    assert request.reason not in evidence

    changed = replace(request, reason="A different reason.")
    with pytest.raises(OrganisationReparentIdempotencyConflict):
        store.replay(replace(command_record, request=changed))
    with engine.begin() as connection, pytest.raises(DBAPIError, match="immutable"):
        connection.execute(
            text(
                "DELETE FROM organisation_unit_closure "
                "WHERE ancestor_unit_id=:ancestor AND descendant_unit_id=:descendant"
            ),
            {"ancestor": target_id, "descendant": moved_id},
        )
    with engine.begin() as connection, pytest.raises(DBAPIError, match="immutable"):
        connection.execute(
            text("SELECT set_config('coeus.organisation_reparent_command',:command_id,true)"),
            {"command_id": str(command_record.command_id)},
        )
        connection.execute(
            text(
                "DELETE FROM organisation_unit_closure "
                "WHERE ancestor_unit_id=:ancestor AND descendant_unit_id=:descendant"
            ),
            {"ancestor": moved_id, "descendant": child_id},
        )
    engine.dispose()


def test_reparent_blocks_silent_grant_broadening_and_stale_target(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, repository, actor_id, _, target_id, moved_id, _ = _tree(postgres_database_url)
    request = _request(engine, repository, moved_id, target_id)
    service = OrganisationReparentService(repository, PostgresOrganisationReparentStore(engine))
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_management_grants(grant_id,manager_user_id,root_unit_id,action,"
                "include_descendants,valid_from,created_by_user_id,reason,delegation_depth,"
                "version) "
                "VALUES (:grant_id,:actor_id,:root_id,'task:view',true,transaction_timestamp(),"
                ":actor_id,'Synthetic target-only authority.',0,1)"
            ),
            {"grant_id": uuid4(), "actor_id": actor_id, "root_id": target_id},
        )
    with pytest.raises(OrganisationReparentConflict, match="broaden"):
        service.preview(request, actor_id)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE team_management_grants SET revoked_at=transaction_timestamp(),version=2 "
                "WHERE root_unit_id=:root_id AND action='task:view'"
            ),
            {"root_id": target_id},
        )
    preview = service.preview(request, actor_id)
    command_record = OrganisationReparentCommand(
        uuid4(), "stale-target-reparent", actor_id, request, preview.preview_hash
    )
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE organisation_units SET version=version + 1 WHERE unit_id=:unit_id"),
            {"unit_id": target_id},
        )
    with pytest.raises(OrganisationReparentConflict, match="parent unit version"):
        service.execute(command_record)
    engine.dispose()
