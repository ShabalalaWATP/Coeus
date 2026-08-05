"""Real PostgreSQL evidence for scheduled single-home personnel transfers."""

import time
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
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationCommand,
    OrganisationMutationOperation,
    OrganisationMutationRequest,
)
from coeus.domain.organisation_transfer import (
    PersonnelTransferCommand,
    PersonnelTransferConflict,
    PersonnelTransferRequest,
    PersonnelTransferStatus,
)
from coeus.persistence.organisation_bootstrap_postgres import (
    PostgresOrganisationBootstrapStore,
)
from coeus.persistence.organisation_lifecycle_postgres import (
    PostgresOrganisationMutationStore,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.organisation_transfer_postgres import PostgresOrganisationTransferStore
from coeus.services.organisation_lifecycle import OrganisationLifecycleService
from coeus.services.organisation_transfer import OrganisationTransferService

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


def _team(engine, repository, lifecycle, actor_id, root_id, name):  # type: ignore[no-untyped-def]
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
        f"Synthetic {name} team.",
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


def _seed_membership(engine, actor_id: UUID, user_id: UUID, unit_id: UUID):  # type: ignore[no-untyped-def]
    membership_id = uuid4()
    valid_from = datetime.now(UTC) - timedelta(days=1)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_memberships(membership_id,user_id,unit_id,role,state,"
                "assignment_eligible,valid_from,created_by_user_id,reason,provenance,version) "
                "VALUES (:membership_id,:user_id,:unit_id,'member','active',true,:valid_from,"
                ":actor_id,'Synthetic source membership.','test',1)"
            ),
            {
                "membership_id": membership_id,
                "user_id": user_id,
                "unit_id": unit_id,
                "valid_from": valid_from,
                "actor_id": actor_id,
            },
        )
    return membership_id, valid_from


def _transfer_request(  # type: ignore[no-untyped-def]
    engine,
    user_id: UUID,
    source_membership_id: UUID,
    source_unit_id: UUID,
    target_unit_id: UUID,
    effective_at: datetime,
) -> PersonnelTransferRequest:
    return PersonnelTransferRequest(
        source_membership_id,
        uuid4(),
        user_id,
        source_unit_id,
        target_unit_id,
        1,
        1,
        MembershipRole.MEMBER,
        True,
        effective_at,
        _grant_id(engine, ManagementAction.ROSTER_TRANSFER),
        _grant_id(engine, ManagementAction.ROSTER_TRANSFER),
        "Move the synthetic analyst to the target team.",
    )


def test_scheduled_transfer_keeps_source_until_atomic_activation(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = _foundation(postgres_database_url)
    source_id = _team(engine, repository, lifecycle, actor_id, root_id, "RFA Alpha")
    target_id = _team(engine, repository, lifecycle, actor_id, root_id, "RFA Bravo")
    user = UserAccount(uuid4(), "analyst1", "Analyst One", frozenset(), frozenset(), "x", True, 3)
    membership_id, _ = _seed_membership(engine, actor_id, user.user_id, source_id)
    effective_at = datetime.now(UTC) + timedelta(seconds=0.75)
    request = _transfer_request(
        engine, user.user_id, membership_id, source_id, target_id, effective_at
    )
    store = PostgresOrganisationTransferStore(engine)
    service = OrganisationTransferService(repository, _Users(user), store)
    preview = service.preview(request, actor_id)
    command_record = PersonnelTransferCommand(
        uuid4(), "transfer-analyst1", actor_id, request, preview.preview_hash
    )
    pending = service.execute(command_record)
    assert pending.status is PersonnelTransferStatus.PENDING
    assert service.execute(command_record).replayed
    assert store.apply(command_record).replayed
    with pytest.raises(ValueError, match="limit"):
        store.due(effective_at, limit=0)
    assert repository.effective_membership(user.user_id, datetime.now(UTC)).unit_id == source_id  # type: ignore[union-attr]
    with pytest.raises(PersonnelTransferConflict, match="not due"):
        store.activate(command_record)

    wait_seconds = max(0.0, (effective_at - datetime.now(UTC)).total_seconds()) + 0.1
    time.sleep(wait_seconds)
    results = service.activate_due()
    assert len(results) == 1 and results[0].status is PersonnelTransferStatus.APPLIED
    assert store.activate(command_record).replayed
    effective = repository.effective_membership(user.user_id, effective_at)
    assert effective is not None and effective.unit_id == target_id
    history = repository.list_memberships(user.user_id)
    assert len(history) == 2
    assert history[0].valid_until == effective_at
    assert history[1].valid_from == effective_at
    with engine.connect() as connection:
        events = set(
            connection.execute(
                text(
                    "SELECT event_type FROM coeus_audit_events "
                    "WHERE event_type LIKE 'organisation_personnel_transfer_%'"
                )
            ).scalars()
        )
    assert events == {
        "organisation_personnel_transfer_pending",
        "organisation_personnel_transfer_applied",
    }
    engine.dispose()


def test_due_transfer_blocks_without_ending_source_when_account_changes(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine, repository, lifecycle, actor_id, root_id = _foundation(postgres_database_url)
    source_id = _team(engine, repository, lifecycle, actor_id, root_id, "CM Alpha")
    target_id = _team(engine, repository, lifecycle, actor_id, root_id, "CM Bravo")
    user = UserAccount(uuid4(), "analyst2", "Analyst Two", frozenset(), frozenset(), "x", True, 3)
    users = _Users(user)
    membership_id, _ = _seed_membership(engine, actor_id, user.user_id, source_id)
    effective_at = datetime.now(UTC) + timedelta(seconds=0.5)
    request = _transfer_request(
        engine, user.user_id, membership_id, source_id, target_id, effective_at
    )
    store = PostgresOrganisationTransferStore(engine)
    service = OrganisationTransferService(repository, users, store)
    preview = service.preview(request, actor_id)
    record = PersonnelTransferCommand(
        uuid4(), "blocked-transfer-analyst2", actor_id, request, preview.preview_hash
    )
    service.execute(record)
    users.user = replace(user, is_active=False)
    wait_seconds = max(0.0, (effective_at - datetime.now(UTC)).total_seconds()) + 0.1
    time.sleep(wait_seconds)
    blocked = service.activate_due()
    assert len(blocked) == 1
    assert blocked[0].status is PersonnelTransferStatus.BLOCKED
    assert blocked[0].failure_code == "account_inactive"
    assert store.block(record, "account_inactive").replayed
    with pytest.raises(ValueError, match="unsupported"):
        store.block(record, "unsafe-free-text")
    missing = replace(record, command_id=uuid4(), idempotency_key="missing-transfer")
    with pytest.raises(PersonnelTransferConflict, match="unavailable"):
        store.block(missing, "state_changed")
    source = repository.list_memberships(user.user_id)
    assert len(source) == 1 and source[0].state.value == "active" and source[0].valid_until is None
    engine.dispose()
