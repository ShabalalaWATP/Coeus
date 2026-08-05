"""Real PostgreSQL evidence for fail-closed organisation deactivation."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text

from coeus.domain.organisation import ManagementAction, OrganisationCategory
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationCommand,
    OrganisationDeactivationConflict,
    OrganisationDeactivationRequest,
)
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
)
from coeus.persistence.organisation_bootstrap_postgres import (
    PostgresOrganisationBootstrapStore,
)
from coeus.persistence.organisation_deactivation_postgres import (
    PostgresOrganisationDeactivationStore,
)
from coeus.persistence.organisation_lifecycle_postgres import (
    PostgresOrganisationMutationStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.services.organisation_deactivation import OrganisationDeactivationService
from coeus.services.organisation_lifecycle import OrganisationLifecycleService

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


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


def _create(engine, repository, lifecycle, actor_id, parent_id, name):  # type: ignore[no-untyped-def]
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
    lifecycle.execute(
        OrganisationMutationCommand(
            uuid4(), f"create-{name.lower()}", actor_id, request, preview.preview_hash
        )
    )
    return unit_id


def _request(engine, repository, unit_id: UUID):  # type: ignore[no-untyped-def]
    unit = repository.get_unit(unit_id)
    assert unit is not None
    return OrganisationDeactivationRequest(
        unit_id,
        unit.version,
        _grant_id(engine, ManagementAction.ORGANISATION_RESTRUCTURE),
        "Deactivate the empty synthetic unit.",
    )


def test_empty_leaf_deactivates_without_deleting_history(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = _foundation(postgres_database_url)
    leaf_id = _create(engine, repository, lifecycle, actor_id, root_id, "Empty Leaf")
    store = PostgresOrganisationDeactivationStore(engine)
    service = OrganisationDeactivationService(repository, store)
    request = _request(engine, repository, leaf_id)
    preview = service.preview(request, actor_id)
    record = OrganisationDeactivationCommand(
        uuid4(), "deactivate-empty-leaf", actor_id, request, preview.preview_hash
    )
    result = service.execute(record)
    assert result.version == 2
    assert service.execute(record).replayed
    assert store.apply(record).replayed
    unit = repository.get_unit(leaf_id)
    assert unit is not None and not unit.is_active and unit.valid_until is not None
    with engine.connect() as connection:
        closure = connection.execute(
            text(
                "SELECT count(*) FROM organisation_unit_closure WHERE descendant_unit_id=:unit_id"
            ),
            {"unit_id": leaf_id},
        ).scalar_one()
        evidence = connection.execute(
            text(
                "SELECT metadata::text FROM coeus_audit_events "
                "WHERE event_type='organisation_unit_deactivated'"
            )
        ).scalar_one()
    assert closure == 2
    assert request.reason not in evidence
    engine.dispose()


def test_deactivation_preview_lists_and_blocks_dependent_subtree(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = _foundation(postgres_database_url)
    parent_id = _create(engine, repository, lifecycle, actor_id, root_id, "Busy Parent")
    _create(engine, repository, lifecycle, actor_id, parent_id, "Active Child")
    service = OrganisationDeactivationService(
        repository, PostgresOrganisationDeactivationStore(engine)
    )
    request = _request(engine, repository, parent_id)
    impact = service._store.inspect(request)  # type: ignore[attr-defined]
    assert impact.active_children == 1 and impact.active_descendants == 1
    with pytest.raises(OrganisationDeactivationConflict, match="dependent"):
        service.preview(request, actor_id)
    engine.dispose()
