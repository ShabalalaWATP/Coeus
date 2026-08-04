"""Real PostgreSQL evidence for previewed organisation create/edit commands."""

from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text

from coeus.domain.organisation import ManagementAction, OrganisationCategory
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationConflict,
    OrganisationMutationIdempotencyConflict,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
    mutation_hash,
)
from coeus.persistence.organisation_bootstrap_postgres import (
    PostgresOrganisationBootstrapStore,
)
from coeus.persistence.organisation_lifecycle_postgres import (
    PostgresOrganisationMutationStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.services.organisation_lifecycle import OrganisationLifecycleService

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
    return engine, actor_id, root_id


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


def test_previewed_create_edit_replay_and_stale_write_protection(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, actor_id, root_id = _foundation(postgres_database_url)
    repository = PostgresOrganisationRepository(engine)
    store = PostgresOrganisationMutationStore(engine)
    service = OrganisationLifecycleService(repository, store)
    child_id = uuid4()
    create_request = OrganisationMutationRequest(
        OrganisationMutationOperation.CREATE,
        child_id,
        root_id,
        1,
        "DI Joint User",
        "DI JU",
        OrganisationCategory.BRANCH,
        "Europe/London",
        "Synthetic child unit.",
        _grant_id(engine, ManagementAction.ORGANISATION_CREATE),
        "Create the synthetic child hierarchy.",
    )
    create_preview = service.preview(create_request, actor_id)
    create_command = OrganisationMutationCommand(
        uuid4(), "create-di-joint-user", actor_id, create_request, create_preview.preview_hash
    )
    created = service.execute(create_command)
    assert created.version == 1
    assert created.topology_revision_id is not None
    assert service.execute(create_command).replayed
    assert store.apply(create_command).replayed

    child = repository.get_unit(child_id)
    assert child is not None
    edit_request = OrganisationMutationRequest(
        OrganisationMutationOperation.EDIT,
        child_id,
        None,
        child.version,
        "DI Joint User Command",
        "DI JUC",
        child.category,
        child.time_zone,
        "Updated synthetic child metadata.",
        _grant_id(engine, ManagementAction.ORGANISATION_EDIT),
        "Correct the synthetic unit metadata.",
    )
    edit_preview = service.preview(edit_request, actor_id)
    edit_command = OrganisationMutationCommand(
        uuid4(), "edit-di-joint-user", actor_id, edit_request, edit_preview.preview_hash
    )
    edited = service.execute(edit_command)
    assert edited.version == 2
    assert edited.topology_revision_id is None

    with engine.connect() as connection:
        path = connection.execute(
            text("SELECT path FROM organisation_topology_revisions WHERE revision_id=:revision_id"),
            {"revision_id": created.topology_revision_id},
        ).scalar_one()
        evidence = set(
            connection.execute(
                text(
                    "SELECT event_type FROM coeus_audit_events "
                    "WHERE event_type LIKE 'organisation_unit_%'"
                )
            ).scalars()
        )
        evidence_payloads = str(
            connection.execute(
                text(
                    "SELECT jsonb_agg(metadata) FROM coeus_audit_events "
                    "WHERE event_type LIKE 'organisation_unit_%'"
                )
            ).scalar_one()
        )
    assert tuple(path) == (root_id, child_id)
    assert evidence == {"organisation_unit_created", "organisation_unit_edited"}
    assert create_request.reason not in evidence_payloads
    assert edit_request.reason not in evidence_payloads
    assert repository.get_unit(child_id).name == "DI Joint User Command"  # type: ignore[union-attr]

    changed = replace(create_request, name="Changed replay payload")
    with pytest.raises(OrganisationMutationIdempotencyConflict):
        service.execute(
            replace(
                create_command,
                request=changed,
                preview_hash=mutation_hash(changed, actor_id),
            )
        )
    with pytest.raises(OrganisationMutationConflict, match="version"):
        service.preview(edit_request, actor_id)
    engine.dispose()


def test_execute_rechecks_grant_after_preview_and_rolls_back(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, actor_id, root_id = _foundation(postgres_database_url)
    repository = PostgresOrganisationRepository(engine)
    store = PostgresOrganisationMutationStore(engine)
    service = OrganisationLifecycleService(repository, store)
    root = repository.get_unit(root_id)
    assert root is not None
    grant_id = _grant_id(engine, ManagementAction.ORGANISATION_EDIT)
    request = OrganisationMutationRequest(
        OrganisationMutationOperation.EDIT,
        root_id,
        None,
        root.version,
        "Renamed Synthetic Root",
        root.short_name,
        root.category,
        root.time_zone,
        root.description,
        grant_id,
        "Synthetic denied edit.",
    )
    preview = service.preview(request, actor_id)
    mutation = OrganisationMutationCommand(
        uuid4(), "revoked-edit", actor_id, request, preview.preview_hash
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE team_management_grants SET revoked_at=transaction_timestamp(),"
                "revoked_by_user_id=:actor_id,revocation_reason='Revoked before execute',"
                "version=version + 1 WHERE grant_id=:grant_id"
            ),
            {"actor_id": actor_id, "grant_id": grant_id},
        )
    with pytest.raises(OrganisationAuthorityDenied):
        store.apply(mutation)
    unchanged = repository.get_unit(root_id)
    assert unchanged is not None and unchanged.name == root.name and unchanged.version == 1
    engine.dispose()
