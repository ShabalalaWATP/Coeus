"""Real PostgreSQL evidence for transactional organisation grant commands."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from coeus.domain.organisation import (
    ManagementAction,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationTopologyRevision,
    OrganisationUnit,
)
from coeus.domain.organisation_authority import (
    CreateManagementGrantCommand,
    OrganisationIdempotencyConflict,
    RevokeManagementGrantCommand,
)
from coeus.persistence.organisation_authority_postgres import (
    PostgresOrganisationGrantCommandStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.services.organisation_authority import (
    OrganisationGrantService,
    OrganisationScopeEvaluator,
)

API_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _account(engine, user_id) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO identity_account_projection"
                "(user_id,is_active,roles,credential_version,source_hash) "
                "VALUES (:user_id,true,ARRAY[]::text[],0,:source_hash)"
            ),
            {"user_id": user_id, "source_hash": "a" * 64},
        )


def _unit(unit_id, name: str, parent_id=None):  # type: ignore[no-untyped-def]
    return OrganisationUnit(
        unit_id,
        name,
        name[:20],
        OrganisationCategory.DELIVERY_TEAM if parent_id else OrganisationCategory.COMMAND,
        parent_id,
        NOW,
    )


def _revision(unit: OrganisationUnit, path):  # type: ignore[no-untyped-def]
    return OrganisationTopologyRevision(
        uuid4(), unit.unit_id, unit.parent_unit_id, path, NOW, uuid4(), uuid4()
    )


def _direct(manager_id, root_id, action):  # type: ignore[no-untyped-def]
    return OrganisationManagementGrant(
        uuid4(), manager_id, root_id, action, True, NOW, manager_id, "Synthetic root authority"
    )


def test_create_revoke_lineage_is_atomic_idempotent_and_immediately_invalidated(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    organisation = PostgresOrganisationRepository(engine)
    commands = PostgresOrganisationGrantCommandStore(engine)
    root = _unit(uuid4(), "Synthetic Command")
    child = _unit(uuid4(), "Synthetic Delivery", root.unit_id)
    organisation.upsert_unit(root, _revision(root, (root.unit_id,)))
    organisation.upsert_unit(child, _revision(child, (root.unit_id, child.unit_id)))

    actor, recipient = uuid4(), uuid4()
    _account(engine, actor)
    manage = _direct(actor, root.unit_id, ManagementAction.GRANT_MANAGE)
    ceiling = _direct(actor, root.unit_id, ManagementAction.TASK_ASSIGN)
    organisation.upsert_management_grant(manage)
    organisation.upsert_management_grant(ceiling)
    service = OrganisationGrantService(organisation, commands, clock=lambda: NOW)
    create_grant_id = uuid4()
    create_command = CreateManagementGrantCommand(
        uuid4(),
        create_grant_id,
        "grant-create-1",
        actor,
        recipient,
        child.unit_id,
        ManagementAction.TASK_ASSIGN,
        False,
        ceiling.grant_id,
        1,
        "Synthetic delegated task assignment",
    )
    created = service.create(create_command)
    assert created.version == 1
    assert service.create(create_command).replayed
    evaluator = OrganisationScopeEvaluator(organisation)
    assert evaluator.evaluate(
        recipient, child.unit_id, ManagementAction.TASK_ASSIGN, datetime.now(UTC)
    ).allowed
    with engine.begin() as connection, pytest.raises(DBAPIError, match="immutable"):
        connection.execute(
            text(
                "UPDATE team_management_grants SET source_grant_id = :source "
                "WHERE grant_id = :grant_id"
            ),
            {"source": manage.grant_id, "grant_id": create_grant_id},
        )

    revoke_command = RevokeManagementGrantCommand(
        uuid4(),
        "grant-revoke-1",
        actor,
        ceiling.grant_id,
        1,
        "Synthetic authority no longer required",
    )
    revoked = service.revoke(revoke_command)
    assert revoked.version == 2
    assert service.revoke(revoke_command).replayed
    assert not evaluator.evaluate(
        recipient, child.unit_id, ManagementAction.TASK_ASSIGN, datetime.now(UTC)
    ).allowed

    with engine.connect() as connection:
        evidence = dict(
            connection.execute(
                text("SELECT event_type, count(*) FROM coeus_audit_events GROUP BY event_type")
            ).all()
        )
        outbox = dict(
            connection.execute(
                text("SELECT event_type, count(*) FROM coeus_outbox GROUP BY event_type")
            ).all()
        )
        epochs = connection.execute(
            text(
                "SELECT principal_id, scope_unit_id, epoch FROM effective_authority_epochs "
                "ORDER BY principal_id, scope_unit_id"
            )
        ).all()
    assert evidence["organisation_grant_created"] == 1
    assert evidence["organisation_grant_revoked"] == 1
    assert outbox["organisation_grant_created"] == 1
    assert outbox["organisation_grant_revoked"] == 1
    assert {(str(row[0]), str(row[1])) for row in epochs} >= {
        (str(actor), str(root.unit_id)),
        (str(recipient), str(child.unit_id)),
    }
    engine.dispose()


def test_reused_idempotency_key_with_changed_payload_fails_closed(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    organisation = PostgresOrganisationRepository(engine)
    root = _unit(uuid4(), "Synthetic Root")
    organisation.upsert_unit(root, _revision(root, (root.unit_id,)))
    actor = uuid4()
    _account(engine, actor)
    manage = _direct(actor, root.unit_id, ManagementAction.GRANT_MANAGE)
    ceiling = _direct(actor, root.unit_id, ManagementAction.TASK_VIEW)
    organisation.upsert_management_grant(manage)
    organisation.upsert_management_grant(ceiling)
    service = OrganisationGrantService(
        organisation, PostgresOrganisationGrantCommandStore(engine), clock=lambda: NOW
    )
    create = CreateManagementGrantCommand(
        uuid4(),
        uuid4(),
        "same-key",
        actor,
        uuid4(),
        root.unit_id,
        ManagementAction.TASK_VIEW,
        False,
        ceiling.grant_id,
        1,
        "Synthetic first grant",
    )
    service.create(create)
    changed = replace(create, command_id=uuid4(), grant_id=uuid4(), reason="Changed payload")
    with pytest.raises(OrganisationIdempotencyConflict):
        service.create(changed)
    engine.dispose()
