"""Refusals a delegated organisation grant command applies before it commits."""

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from test_organisation_authority_postgres import NOW, _account, _direct, _revision, _unit, _upgrade

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import (
    CreateManagementGrantCommand,
    OrganisationAuthorityConflict,
    OrganisationAuthorityDenied,
    RevokeManagementGrantCommand,
)
from coeus.persistence.organisation_authority_postgres import (
    PostgresOrganisationGrantCommandStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.services.organisation_authority import OrganisationGrantService

pytestmark = pytest.mark.postgres


def _fixture(database_url: str):  # type: ignore[no-untyped-def]
    _upgrade(database_url)
    engine = create_engine(database_url)
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
    return engine, service, child, actor, recipient, ceiling


def _create(child, actor, recipient, ceiling, **overrides):  # type: ignore[no-untyped-def]
    command = CreateManagementGrantCommand(
        uuid4(),
        uuid4(),
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
    return replace(command, **overrides)


def test_a_grant_identity_may_only_be_created_once(postgres_database_url: str) -> None:
    engine, service, child, actor, recipient, ceiling = _fixture(postgres_database_url)
    command = _create(child, actor, recipient, ceiling)
    service.create(command)

    with pytest.raises(OrganisationAuthorityConflict, match="grant identity already exists"):
        service.create(replace(command, command_id=uuid4(), idempotency_key="grant-create-2"))
    engine.dispose()


def test_a_stale_source_version_refuses_the_delegation(postgres_database_url: str) -> None:
    engine, service, child, actor, recipient, ceiling = _fixture(postgres_database_url)

    with pytest.raises(OrganisationAuthorityConflict, match="source grant version"):
        service.create(_create(child, actor, recipient, ceiling, expected_source_version=9))
    engine.dispose()


def test_a_delegation_without_a_current_source_is_denied(postgres_database_url: str) -> None:
    engine, service, child, actor, recipient, ceiling = _fixture(postgres_database_url)

    with pytest.raises((OrganisationAuthorityDenied, OrganisationAuthorityConflict)):
        service.create(_create(child, actor, recipient, ceiling, source_grant_id=uuid4()))
    engine.dispose()


def test_an_unknown_grant_cannot_be_revoked(postgres_database_url: str) -> None:
    engine, service, _, actor, _, _ = _fixture(postgres_database_url)

    with pytest.raises(OrganisationAuthorityConflict, match="no longer"):
        service.revoke(
            RevokeManagementGrantCommand(uuid4(), "revoke-1", actor, uuid4(), 1, "No longer needed")
        )
    engine.dispose()


def test_a_stale_expected_version_cannot_revoke(postgres_database_url: str) -> None:
    engine, service, _, actor, _, ceiling = _fixture(postgres_database_url)

    with pytest.raises(OrganisationAuthorityConflict, match="version is no longer current"):
        service.revoke(
            RevokeManagementGrantCommand(
                uuid4(), "revoke-1", actor, ceiling.grant_id, 9, "No longer needed"
            )
        )
    engine.dispose()


def test_an_already_revoked_grant_cannot_be_revoked_again(postgres_database_url: str) -> None:
    engine, service, _, actor, _, ceiling = _fixture(postgres_database_url)
    service.revoke(
        RevokeManagementGrantCommand(
            uuid4(), "revoke-1", actor, ceiling.grant_id, 1, "No longer needed"
        )
    )

    with pytest.raises(OrganisationAuthorityConflict, match="version is no longer current"):
        service.revoke(
            RevokeManagementGrantCommand(uuid4(), "revoke-2", actor, ceiling.grant_id, 2, "Again")
        )
    engine.dispose()


def test_an_expired_grant_cannot_be_revoked(postgres_database_url: str) -> None:
    engine, service, _, actor, _, ceiling = _fixture(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE team_management_grants SET valid_until=valid_from+interval '1 second' "
                "WHERE grant_id=:grant_id"
            ),
            {"grant_id": ceiling.grant_id},
        )

    with pytest.raises(OrganisationAuthorityConflict, match="expired grant cannot be revoked"):
        service.revoke(
            RevokeManagementGrantCommand(
                uuid4(), "revoke-1", actor, ceiling.grant_id, 1, "No longer needed"
            )
        )
    engine.dispose()
