"""Real PostgreSQL proof for workspace productivity authority and idempotence."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.team_task_board import TeamBoardColumn
from coeus.domain.workspace_productivity import ProductivityCommand
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.workspace_productivity_postgres import PostgresWorkspaceProductivityStore

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def test_saved_views_templates_and_updates_recheck_current_authority(
    postgres_database_url: str,
) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    actor, bootstrap_actor, root_id = uuid4(), uuid4(), uuid4()
    foundation = PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), bootstrap_actor, root_id, "Synthetic Team", "SYN", "Europe/London", ""
        )
    )
    activate_principals(engine, actor, bootstrap_actor)
    grants = _seed_authority(engine, actor, root_id)
    ticket_id = _seed_ticket_ownership(engine, actor, root_id, foundation.topology_revision_id)
    store = PostgresWorkspaceProductivityStore(engine)
    view_id = uuid4()
    view = store.save_view(
        _command(
            actor,
            "save_view",
            {
                "view_id": view_id,
                "unit_id": root_id,
                "name": "Urgent work",
                "expected_version": 0,
                "filters": {"columns": [TeamBoardColumn.IN_PROGRESS.value]},
            },
        )
    )
    assert view.name == "Urgent work"
    assert store.list_views(actor, None, 10).items == (view,)

    template = store.save_template(
        _command(
            actor,
            "save_template",
            {
                "template_id": uuid4(),
                "unit_id": root_id,
                "name": "Assessment",
                "package_titles": ["Research", "Draft"],
                "estimated_minutes": 120,
                "priority": 2,
                "expected_version": 0,
                "authorising_grant_id": grants["workspace:configure"],
                "expected_grant_version": 1,
            },
        )
    )
    assert store.list_templates(actor, root_id, None, 10).items == (template,)

    link = store.save_store_link(
        _command(
            actor,
            "save_store_link",
            {
                "link_id": uuid4(),
                "unit_id": root_id,
                "source_type": "ticket",
                "source_id": ticket_id,
                "target_type": "product",
                "target_id": uuid4(),
                "label": "Policy-validated report",
                "expected_version": 0,
            },
        )
    )
    assert store.list_store_links(actor, root_id, "ticket", ticket_id, None, 10).items == (link,)

    event_key, update_id = "ticket-assigned:1", uuid4()
    delivery_payload = {
        "update_id": update_id,
        "recipient_user_id": actor,
        "event_key": event_key,
        "kind": "assignment",
        "unit_id": root_id,
        "object_type": "ticket",
        "object_id": ticket_id,
        "authorising_grant_id": grants["workspace:configure"],
        "expected_grant_version": 1,
    }
    first = store.deliver_update(_command(actor, "deliver_update", delivery_payload))
    duplicate = store.deliver_update(_command(actor, "deliver_update", delivery_payload))
    assert first.update_id == duplicate.update_id == update_id
    assert len(store.list_updates(actor, None, 10, False).items) == 1
    acknowledged = store.acknowledge_update(
        _command(actor, "acknowledge_update", {"update_id": update_id})
    )
    assert acknowledged.acknowledged_at is not None

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE team_management_grants SET revoked_at=now(),version=version+1 "
                "WHERE grant_id=:grant"
            ),
            {"grant": grants["task:view"]},
        )
    assert store.list_views(actor, None, 10).items == ()
    assert store.list_updates(actor, None, 10, False).items == ()
    with pytest.raises(PermissionError):
        store.list_store_links(actor, root_id, "ticket", ticket_id, None, 10)
    engine.dispose()


def _command(actor: UUID, operation: str, payload: dict[str, object]) -> ProductivityCommand:
    return ProductivityCommand(uuid4(), str(uuid4()), actor, operation, payload)


def _seed_authority(engine: Engine, actor: UUID, unit_id: UUID) -> dict[str, UUID]:
    now, grants = datetime.now(UTC), {}
    with engine.begin() as connection:
        for action in (
            "workspace:view",
            "workspace:configure",
            "task:view",
            "work_update:view",
        ):
            grant_id = uuid4()
            grants[action] = grant_id
            connection.execute(
                text(
                    "INSERT INTO team_management_grants"
                    "(grant_id,manager_user_id,root_unit_id,action,include_descendants,"
                    "valid_from,created_by_user_id,reason,delegation_depth,version) VALUES "
                    "(:grant,:actor,:unit,:action,false,:at,:actor,'test',0,1)"
                ),
                {
                    "grant": grant_id,
                    "actor": actor,
                    "unit": unit_id,
                    "action": action,
                    "at": now,
                },
            )
    return grants


def _seed_ticket_ownership(engine: Engine, actor: UUID, unit_id: UUID, revision_id: UUID) -> UUID:
    ticket_id, now = uuid4(), datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_task_ownership"
                "(ownership_id,ticket_id,workflow_leg,owning_unit_id,manager_user_id,state,"
                "accepted_at,topology_revision_id,capability_policy_version,version,"
                "history_reference,provenance,created_at,updated_at) VALUES "
                "(:id,:ticket,'rfa',:unit,:actor,'active',:at,:revision,1,1,:history,'test',:at,:at)"
            ),
            {
                "id": uuid4(),
                "ticket": ticket_id,
                "unit": unit_id,
                "actor": actor,
                "at": now,
                "revision": revision_id,
                "history": uuid4(),
            },
        )
    return ticket_id
