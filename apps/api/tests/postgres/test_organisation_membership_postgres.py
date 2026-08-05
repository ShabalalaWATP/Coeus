"""Real PostgreSQL evidence for single-home membership lifecycle commands."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text

from coeus.domain.auth import UserAccount
from coeus.domain.organisation import ManagementAction, MembershipRole, OrganisationCategory
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
)
from coeus.domain.organisation_membership import (
    MembershipCommandConflict,
    MembershipMutationCommand,
    MembershipMutationRequest,
    MembershipOperation,
)
from coeus.persistence.organisation_bootstrap_postgres import (
    PostgresOrganisationBootstrapStore,
)
from coeus.persistence.organisation_lifecycle_postgres import (
    PostgresOrganisationMutationStore,
)
from coeus.persistence.organisation_membership_postgres import (
    PostgresOrganisationMembershipStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.services.organisation_lifecycle import OrganisationLifecycleService
from coeus.services.organisation_membership import OrganisationMembershipService

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


class _Users:
    def __init__(self, user: UserAccount) -> None:
        self.user = user

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self.user if self.user.user_id == user_id else None


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


def _delivery_unit(  # type: ignore[no-untyped-def]
    engine,
    repository: PostgresOrganisationRepository,
    lifecycle: OrganisationLifecycleService,
    actor_id: UUID,
    root_id: UUID,
    name: str,
) -> UUID:
    root = repository.get_unit(root_id)
    assert root is not None
    unit_id = uuid4()
    request = OrganisationMutationRequest(
        OrganisationMutationOperation.CREATE,
        unit_id,
        root_id,
        root.version,
        name,
        name[:12],
        OrganisationCategory.DELIVERY_TEAM,
        "Europe/London",
        f"Synthetic {name} delivery team.",
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


def _request(  # type: ignore[no-untyped-def]
    engine,
    user_id: UUID,
    unit_id: UUID,
    membership_id: UUID,
    valid_from: datetime,
) -> MembershipMutationRequest:
    return MembershipMutationRequest(
        MembershipOperation.CREATE,
        membership_id,
        user_id,
        unit_id,
        0,
        MembershipRole.MEMBER,
        True,
        valid_from,
        None,
        _grant_id(engine, ManagementAction.ROSTER_MANAGE),
        "Create the synthetic analyst home membership.",
    )


def test_membership_create_update_end_and_exact_boundary_rejoin(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = _foundation(postgres_database_url)
    first_id = _delivery_unit(engine, repository, lifecycle, actor_id, root_id, "RFA Alpha")
    second_id = _delivery_unit(engine, repository, lifecycle, actor_id, root_id, "RFA Bravo")
    now = datetime.now(UTC)
    user = UserAccount(uuid4(), "analyst1", "Analyst One", frozenset(), frozenset(), "x", True, 3)
    users = _Users(user)
    store = PostgresOrganisationMembershipStore(engine)
    service = OrganisationMembershipService(
        repository, users, store, clock=lambda: now + timedelta(seconds=1)
    )
    request = _request(engine, user.user_id, first_id, uuid4(), now - timedelta(hours=1))
    preview = service.preview(request, actor_id)
    create_record = MembershipMutationCommand(
        uuid4(), "create-analyst1-home", actor_id, request, preview.preview_hash
    )
    assert service.execute(create_record).version == 1
    assert service.execute(create_record).replayed
    assert store.apply(create_record).replayed

    overlapping = _request(engine, user.user_id, second_id, uuid4(), now)
    overlap_preview = service.preview(overlapping, actor_id)
    with pytest.raises(MembershipCommandConflict, match="overlapping"):
        service.execute(
            MembershipMutationCommand(
                uuid4(),
                "overlap-analyst1-home",
                actor_id,
                overlapping,
                overlap_preview.preview_hash,
            )
        )

    update = replace(
        request,
        operation=MembershipOperation.UPDATE,
        expected_version=1,
        role=MembershipRole.DEPUTY,
        reason="Make the synthetic analyst a deputy.",
    )
    update_preview = service.preview(update, actor_id)
    assert (
        service.execute(
            MembershipMutationCommand(
                uuid4(), "update-analyst1-home", actor_id, update, update_preview.preview_hash
            )
        ).version
        == 2
    )

    end_at = now
    ending = replace(
        update,
        operation=MembershipOperation.END,
        expected_version=2,
        assignment_eligible=False,
        valid_until=end_at,
        reason="End the synthetic home membership.",
    )
    end_preview = service.preview(ending, actor_id)
    assert (
        service.execute(
            MembershipMutationCommand(
                uuid4(), "end-analyst1-home", actor_id, ending, end_preview.preview_hash
            )
        ).version
        == 3
    )

    replacement = _request(engine, user.user_id, second_id, uuid4(), end_at)
    replacement_preview = service.preview(replacement, actor_id)
    assert (
        service.execute(
            MembershipMutationCommand(
                uuid4(),
                "replace-analyst1-home",
                actor_id,
                replacement,
                replacement_preview.preview_hash,
            )
        ).version
        == 1
    )
    effective = repository.effective_membership(user.user_id, end_at)
    assert effective is not None and effective.unit_id == second_id
    with engine.connect() as connection:
        events = set(
            connection.execute(
                text(
                    "SELECT event_type FROM coeus_audit_events "
                    "WHERE event_type LIKE 'organisation_membership_%'"
                )
            ).scalars()
        )
    assert events == {
        "organisation_membership_created",
        "organisation_membership_updated",
        "organisation_membership_ended",
    }
    engine.dispose()


def test_execute_rechecks_account_and_database_grant(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = _foundation(postgres_database_url)
    unit_id = _delivery_unit(engine, repository, lifecycle, actor_id, root_id, "CM Alpha")
    now = datetime.now(UTC)
    user = UserAccount(uuid4(), "analyst2", "Analyst Two", frozenset(), frozenset(), "x", True, 3)
    users = _Users(user)
    store = PostgresOrganisationMembershipStore(engine)
    service = OrganisationMembershipService(repository, users, store, clock=lambda: now)
    request = _request(engine, user.user_id, unit_id, uuid4(), now - timedelta(hours=1))
    preview = service.preview(request, actor_id)
    command_record = MembershipMutationCommand(
        uuid4(), "account-recheck-membership", actor_id, request, preview.preview_hash
    )
    users.user = replace(user, is_active=False)
    with pytest.raises(MembershipCommandConflict, match="account"):
        service.execute(command_record)
    users.user = user
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE team_management_grants SET revoked_at=transaction_timestamp(),version=2 "
                "WHERE grant_id=:grant_id"
            ),
            {"grant_id": request.authorising_grant_id},
        )
    with pytest.raises(OrganisationAuthorityDenied):
        store.apply(command_record)
    assert repository.list_memberships(user.user_id) == ()
    engine.dispose()
