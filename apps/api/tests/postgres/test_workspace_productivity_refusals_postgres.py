"""Refusal and update paths for saved views, templates, links and updates."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from workspace_operations_support import seed_authority

from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.workspace_productivity import (
    ProductivityCommand,
    WorkspaceRecordConflict,
    WorkspaceRecordDenied,
)
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.workspace_productivity_postgres import PostgresWorkspaceProductivityStore

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres

ACTIONS = ("workspace:view", "workspace:configure", "task:view", "work_update:view")


def _setup(database_url: str) -> tuple[Engine, UUID, UUID, dict[str, UUID]]:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    actor, bootstrap_actor, root_id = uuid4(), uuid4(), uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), bootstrap_actor, root_id, "Synthetic Team", "SYN", "Europe/London", ""
        )
    )
    activate_principals(engine, actor, bootstrap_actor)
    grants = seed_authority(engine, actor, root_id, ACTIONS)
    return engine, actor, root_id, grants


def _command(actor: UUID, operation: str, payload: dict[str, object]) -> ProductivityCommand:
    return ProductivityCommand(uuid4(), str(uuid4()), actor, operation, payload)


def test_saved_views_enforce_ownership_versions_and_deletion(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, _ = _setup(postgres_database_url)
    store = PostgresWorkspaceProductivityStore(engine)
    view_id = uuid4()

    def payload(**overrides: object) -> dict[str, object]:
        return {
            "view_id": view_id,
            "unit_id": root_id,
            "name": "Urgent work",
            "expected_version": 0,
            "filters": {"columns": ["in_progress"]},
            **overrides,
        }

    with pytest.raises(WorkspaceRecordConflict, match="saved view version changed"):
        store.save_view(_command(actor, "save_view", payload(expected_version=3)))

    created = store.save_view(_command(actor, "save_view", payload()))
    assert created.version == 1

    updated = store.save_view(
        _command(actor, "save_view", payload(expected_version=1, name="Renamed"))
    )
    assert updated.name == "Renamed" and updated.version == 2

    with pytest.raises(WorkspaceRecordConflict, match="saved view version changed"):
        store.save_view(_command(actor, "save_view", payload(expected_version=1)))

    # Ownership is per person, so another manager cannot overwrite or delete it.
    other = uuid4()
    activate_principals(engine, other)
    seed_authority(engine, other, root_id, ACTIONS)
    with pytest.raises(WorkspaceRecordDenied):
        store.save_view(_command(other, "save_view", payload(expected_version=2)))
    with pytest.raises(WorkspaceRecordDenied):
        store.delete_view(
            _command(other, "delete_view", {"view_id": view_id, "expected_version": 2})
        )
    with pytest.raises(WorkspaceRecordDenied):
        store.delete_view(
            _command(actor, "delete_view", {"view_id": uuid4(), "expected_version": 0})
        )

    assert store.delete_view(
        _command(actor, "delete_view", {"view_id": view_id, "expected_version": 2})
    )
    assert store.list_views(actor, None, 10).items == ()
    engine.dispose()


def test_package_templates_validate_titles_versions_and_ownership(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, grants = _setup(postgres_database_url)
    store = PostgresWorkspaceProductivityStore(engine)
    template_id = uuid4()

    def payload(**overrides: object) -> dict[str, object]:
        return {
            "template_id": template_id,
            "unit_id": root_id,
            "name": "Assessment",
            "package_titles": ["Research", "Draft"],
            "estimated_minutes": 120,
            "priority": 2,
            "expected_version": 0,
            "authorising_grant_id": grants["workspace:configure"],
            "expected_grant_version": 1,
            **overrides,
        }

    with pytest.raises(ValueError, match="package titles are invalid"):
        store.save_template(_command(actor, "save_template", payload(package_titles="Research")))
    with pytest.raises(WorkspaceRecordConflict, match="template version changed"):
        store.save_template(_command(actor, "save_template", payload(expected_version=4)))

    created = store.save_template(_command(actor, "save_template", payload()))
    assert created.version == 1

    updated = store.save_template(
        _command(actor, "save_template", payload(expected_version=1, name="Deep assessment"))
    )
    assert updated.name == "Deep assessment" and updated.version == 2

    other = uuid4()
    activate_principals(engine, other)
    other_grants = seed_authority(engine, other, root_id, ACTIONS)
    with pytest.raises(WorkspaceRecordDenied):
        store.save_template(
            _command(
                other,
                "save_template",
                payload(
                    expected_version=2,
                    authorising_grant_id=other_grants["workspace:configure"],
                ),
            )
        )
    with pytest.raises(WorkspaceRecordDenied):
        store.delete_template(
            _command(
                actor,
                "delete_template",
                {
                    "template_id": uuid4(),
                    "expected_version": 0,
                    "authorising_grant_id": grants["workspace:configure"],
                    "expected_grant_version": 1,
                },
            )
        )

    assert store.delete_template(
        _command(
            actor,
            "delete_template",
            {
                "template_id": template_id,
                "expected_version": 2,
                "authorising_grant_id": grants["workspace:configure"],
                "expected_grant_version": 1,
            },
        )
    )
    assert store.list_templates(actor, root_id, None, 10).items == ()
    engine.dispose()


def test_store_links_require_current_authority_and_exact_versions(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, _ = _setup(postgres_database_url)
    store = PostgresWorkspaceProductivityStore(engine)
    link_id, source_id = uuid4(), uuid4()
    _seed_ownership(engine, actor, root_id, source_id)

    def payload(**overrides: object) -> dict[str, object]:
        return {
            "link_id": link_id,
            "unit_id": root_id,
            "source_type": "ticket",
            "source_id": source_id,
            "target_type": "product",
            "target_id": uuid4(),
            "label": "Policy-validated report",
            "expected_version": 0,
            **overrides,
        }

    with pytest.raises(WorkspaceRecordConflict):
        store.save_store_link(_command(actor, "save_store_link", payload(expected_version=6)))

    created = store.save_store_link(_command(actor, "save_store_link", payload()))
    assert created.version == 1

    other = uuid4()
    activate_principals(engine, other)
    seed_authority(engine, other, root_id, ACTIONS)
    with pytest.raises(WorkspaceRecordDenied):
        store.delete_store_link(
            _command(other, "delete_store_link", {"link_id": link_id, "expected_version": 1})
        )
    with pytest.raises(WorkspaceRecordDenied):
        store.delete_store_link(
            _command(actor, "delete_store_link", {"link_id": uuid4(), "expected_version": 0})
        )

    assert store.delete_store_link(
        _command(actor, "delete_store_link", {"link_id": link_id, "expected_version": 1})
    )
    engine.dispose()


def test_work_updates_are_recipient_scoped_and_acknowledged_once(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, grants = _setup(postgres_database_url)
    store = PostgresWorkspaceProductivityStore(engine)
    update_id, ticket_id = uuid4(), uuid4()
    _seed_ownership(engine, actor, root_id, ticket_id)

    delivered = store.deliver_update(
        _command(
            actor,
            "deliver_update",
            {
                "update_id": update_id,
                "recipient_user_id": actor,
                "event_key": "ticket-assigned:1",
                "kind": "assignment",
                "unit_id": root_id,
                "object_type": "ticket",
                "object_id": ticket_id,
                "authorising_grant_id": grants["workspace:configure"],
                "expected_grant_version": 1,
            },
        )
    )
    assert delivered.acknowledged_at is None

    other = uuid4()
    activate_principals(engine, other)
    with pytest.raises(WorkspaceRecordDenied):
        store.acknowledge_update(_command(other, "acknowledge_update", {"update_id": update_id}))
    with pytest.raises(WorkspaceRecordDenied):
        store.acknowledge_update(_command(actor, "acknowledge_update", {"update_id": uuid4()}))

    first = store.acknowledge_update(
        _command(actor, "acknowledge_update", {"update_id": update_id})
    )
    assert first.acknowledged_at is not None
    # It stays readable in the full list but leaves the unacknowledged view.
    assert len(store.list_updates(actor, None, 10, False).items) == 1
    assert store.list_updates(actor, None, 10, True).items == ()
    engine.dispose()


def _seed_ownership(engine: Engine, actor: UUID, unit_id: UUID, ticket_id: UUID) -> None:
    with engine.begin() as connection:
        revision = connection.execute(
            text(
                "SELECT revision_id FROM organisation_topology_revisions "
                "ORDER BY created_at LIMIT 1"
            )
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO team_task_ownership"
                "(ownership_id,ticket_id,workflow_leg,owning_unit_id,manager_user_id,state,"
                "accepted_at,topology_revision_id,capability_policy_version,version,"
                "history_reference,provenance,created_at,updated_at) VALUES "
                "(:id,:ticket,'rfa',:unit,:actor,'active',now(),:revision,1,1,:history,"
                "'test',now(),now())"
            ),
            {
                "id": uuid4(),
                "ticket": ticket_id,
                "unit": unit_id,
                "actor": actor,
                "revision": revision,
                "history": uuid4(),
            },
        )
