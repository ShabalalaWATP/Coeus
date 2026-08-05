"""Command-store level replay and evidence checks for organisation grants."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from test_organisation_authority_postgres import NOW, _account, _direct, _revision, _unit, _upgrade

from coeus.domain.organisation import ManagementAction, OrganisationManagementGrant
from coeus.domain.organisation_authority import (
    OrganisationAuthorityConflict,
    OrganisationAuthorityDenied,
    RevokeManagementGrantCommand,
)
from coeus.persistence.organisation_authority_postgres import (
    PostgresOrganisationGrantCommandStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository

pytestmark = pytest.mark.postgres
HASH = "a" * 64


def _fixture(database_url: str):  # type: ignore[no-untyped-def]
    _upgrade(database_url)
    engine = create_engine(database_url)
    organisation = PostgresOrganisationRepository(engine)
    store = PostgresOrganisationGrantCommandStore(engine)
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
    return engine, store, child, actor, recipient, manage, ceiling


def _delegated(recipient, child, ceiling, actor):  # type: ignore[no-untyped-def]
    return OrganisationManagementGrant(
        uuid4(),
        recipient,
        child.unit_id,
        ManagementAction.TASK_ASSIGN,
        False,
        NOW,
        actor,
        "Synthetic delegated task assignment",
        source_grant_id=ceiling.grant_id,
        delegation_depth=1,
    )


def _create(store, grant, actor, manage, **overrides):  # type: ignore[no-untyped-def]
    values: dict[str, object] = {
        "command_id": uuid4(),
        "idempotency_key": "grant-create-1",
        "request_hash": HASH,
        "actor_user_id": actor,
        "management_grant_id": manage.grant_id,
        "source_expected_version": 1,
        "occurred_at": datetime.now(UTC),
    }
    values.update(overrides)
    return store.create_grant(grant, **values)


def test_the_store_replays_a_repeated_create_without_writing_again(
    postgres_database_url: str,
) -> None:
    engine, store, child, actor, recipient, manage, ceiling = _fixture(postgres_database_url)
    grant = _delegated(recipient, child, ceiling, actor)
    command_id = uuid4()

    first = _create(store, grant, actor, manage, command_id=command_id)
    replayed = _create(store, grant, actor, manage, command_id=command_id)

    assert not first.replayed and replayed.replayed
    assert first.version == replayed.version
    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM team_management_grants WHERE grant_id=:grant"),
            {"grant": grant.grant_id},
        ).scalar_one()
    assert count == 1
    engine.dispose()


def test_a_delegated_grant_without_a_source_is_denied(postgres_database_url: str) -> None:
    engine, store, child, actor, recipient, manage, ceiling = _fixture(postgres_database_url)
    # The domain refuses a depth without a source, so the store's own refusal is
    # only reachable with a root-depth grant that names no source.
    grant = replace(
        _delegated(recipient, child, ceiling, actor), source_grant_id=None, delegation_depth=0
    )

    with pytest.raises(OrganisationAuthorityDenied, match="requires a source"):
        _create(store, grant, actor, manage)
    engine.dispose()


def test_a_stale_source_version_is_refused_by_the_store(postgres_database_url: str) -> None:
    engine, store, child, actor, recipient, manage, ceiling = _fixture(postgres_database_url)
    grant = _delegated(recipient, child, ceiling, actor)

    with pytest.raises(OrganisationAuthorityConflict, match="source grant version"):
        _create(store, grant, actor, manage, source_expected_version=9)
    engine.dispose()


def test_the_store_replays_a_repeated_revoke(postgres_database_url: str) -> None:
    engine, store, _, actor, _, manage, ceiling = _fixture(postgres_database_url)
    command = RevokeManagementGrantCommand(
        uuid4(), "grant-revoke-1", actor, ceiling.grant_id, 1, "No longer required"
    )

    first = store.revoke_grant(
        command,
        request_hash=HASH,
        management_grant_id=manage.grant_id,
        occurred_at=datetime.now(UTC),
    )
    replayed = store.revoke_grant(
        command,
        request_hash=HASH,
        management_grant_id=manage.grant_id,
        occurred_at=datetime.now(UTC),
    )

    assert not first.replayed and replayed.replayed
    assert first.version == replayed.version == 2
    engine.dispose()


def test_the_store_refuses_to_revoke_an_unknown_grant(postgres_database_url: str) -> None:
    engine, store, _, actor, _, manage, _ = _fixture(postgres_database_url)
    command = RevokeManagementGrantCommand(
        uuid4(), "grant-revoke-1", actor, uuid4(), 1, "No longer required"
    )

    with pytest.raises(OrganisationAuthorityConflict, match="grant no longer exists"):
        store.revoke_grant(
            command,
            request_hash=HASH,
            management_grant_id=manage.grant_id,
            occurred_at=datetime.now(UTC),
        )
    engine.dispose()
