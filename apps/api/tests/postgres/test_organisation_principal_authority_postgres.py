"""PostgreSQL evidence for account-aware grant lineage authority."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from coeus.domain.jioc_principals import JIOC_AGENT_PRINCIPAL
from coeus.domain.organisation import (
    ManagementAction,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationTopologyRevision,
    OrganisationUnit,
)
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.persistence.organisation_authority_validation import validate_lineage
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _account(connection, user_id, *, active: bool = True) -> None:  # type: ignore[no-untyped-def]
    connection.execute(
        text(
            "INSERT INTO identity_account_projection"
            "(user_id,is_active,roles,credential_version,source_hash) "
            "VALUES (:user_id,:active,ARRAY[]::text[],0,:source_hash)"
        ),
        {"user_id": user_id, "active": active, "source_hash": "a" * 64},
    )


def _foundation(engine):  # type: ignore[no-untyped-def]
    now = datetime.now(UTC)
    repository = PostgresOrganisationRepository(engine)
    root = OrganisationUnit(
        uuid4(),
        "Synthetic authority root",
        "Authority root",
        OrganisationCategory.COMMAND,
        None,
        now,
    )
    repository.upsert_unit(
        root,
        OrganisationTopologyRevision(
            uuid4(), root.unit_id, None, (root.unit_id,), now, uuid4(), uuid4()
        ),
    )
    root_creator, upstream, holder = uuid4(), uuid4(), uuid4()
    source = OrganisationManagementGrant(
        uuid4(),
        upstream,
        root.unit_id,
        ManagementAction.TASK_VIEW,
        True,
        now,
        root_creator,
        "Synthetic root authority",
    )
    leaf = OrganisationManagementGrant(
        uuid4(),
        holder,
        root.unit_id,
        ManagementAction.TASK_VIEW,
        False,
        now,
        upstream,
        "Synthetic delegated authority",
        source_grant_id=source.grant_id,
        delegation_depth=1,
    )
    repository.upsert_management_grant(source)
    repository.upsert_management_grant(leaf)
    with engine.begin() as connection:
        _account(connection, upstream)
        _account(connection, holder)
        _account(connection, root_creator)
    return root, source, leaf, root_creator, upstream, holder


def test_suspended_or_missing_human_invalidates_the_whole_lineage(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    root, _, leaf, root_creator, upstream, holder = _foundation(engine)
    with engine.begin() as connection:
        validate_lineage(
            connection,
            leaf.grant_id,
            holder,
            root.unit_id,
            ManagementAction.TASK_VIEW,
            datetime.now(UTC),
        )
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:user_id"),
            {"user_id": root_creator},
        )
    with (
        engine.begin() as connection,
        pytest.raises(OrganisationAuthorityDenied, match="missing or suspended"),
    ):
        validate_lineage(
            connection,
            leaf.grant_id,
            holder,
            root.unit_id,
            ManagementAction.TASK_VIEW,
            datetime.now(UTC),
        )
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=true WHERE user_id=:user_id"),
            {"user_id": root_creator},
        )
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:user_id"),
            {"user_id": upstream},
        )
    with (
        engine.begin() as connection,
        pytest.raises(OrganisationAuthorityDenied, match="missing or suspended"),
    ):
        validate_lineage(
            connection,
            leaf.grant_id,
            holder,
            root.unit_id,
            ManagementAction.TASK_VIEW,
            datetime.now(UTC),
        )
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=true WHERE user_id=:user_id"),
            {"user_id": upstream},
        )
        connection.execute(
            text("DELETE FROM identity_account_projection WHERE user_id=:user_id"),
            {"user_id": holder},
        )
    with (
        engine.begin() as connection,
        pytest.raises(OrganisationAuthorityDenied, match="missing or suspended"),
    ):
        validate_lineage(
            connection,
            leaf.grant_id,
            holder,
            root.unit_id,
            ManagementAction.TASK_VIEW,
            datetime.now(UTC),
        )
    engine.dispose()


def test_registered_service_is_explicit_and_human_status_is_transaction_locked(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    root, _, leaf, _, _, holder = _foundation(engine)
    service_grant = OrganisationManagementGrant(
        uuid4(),
        JIOC_AGENT_PRINCIPAL,
        root.unit_id,
        ManagementAction.RECOMMENDATION_VIEW,
        True,
        datetime.now(UTC),
        JIOC_AGENT_PRINCIPAL,
        "Synthetic registered service authority",
    )
    PostgresOrganisationRepository(engine).upsert_management_grant(service_grant)
    with engine.begin() as connection:
        validate_lineage(
            connection,
            service_grant.grant_id,
            JIOC_AGENT_PRINCIPAL,
            root.unit_id,
            ManagementAction.RECOMMENDATION_VIEW,
            datetime.now(UTC),
        )

    with engine.connect() as authority_connection:
        authority_transaction = authority_connection.begin()
        validate_lineage(
            authority_connection,
            leaf.grant_id,
            holder,
            root.unit_id,
            ManagementAction.TASK_VIEW,
            datetime.now(UTC),
        )
        with pytest.raises(DBAPIError, match="lock timeout"), engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='100ms'"))
            connection.execute(
                text(
                    "UPDATE identity_account_projection SET is_active=false WHERE user_id=:user_id"
                ),
                {"user_id": holder},
            )
        authority_transaction.commit()

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:user_id"),
            {"user_id": holder},
        )
    with (
        engine.begin() as connection,
        pytest.raises(OrganisationAuthorityDenied, match="missing or suspended"),
    ):
        validate_lineage(
            connection,
            leaf.grant_id,
            holder,
            root.unit_id,
            ManagementAction.TASK_VIEW,
            datetime.now(UTC),
        )
    engine.dispose()
