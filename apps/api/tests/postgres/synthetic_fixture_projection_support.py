"""Real-PostgreSQL personal-work and capacity checks for the synthetic fixture."""

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from coeus.domain.synthetic_organisation_fixture import SyntheticFixtureUser
from coeus.persistence.jioc_routing_context_postgres import (
    RELATIONAL_CONTEXT_VERSION,
    PostgresShadowRoutingOperationalContext,
)
from coeus.persistence.my_work_postgres import PostgresMyWorkStore
from coeus.persistence.team_capacity_forecast_postgres import (
    PostgresTeamCapacityForecastStore,
)
from coeus.repositories.synthetic_organisation_manifest import (
    synthetic_posting_specs,
    synthetic_unit_specs,
)
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs
from coeus.repositories.synthetic_workforce import synthetic_user_id


def assert_fixture_projections(engine: Engine, users: tuple[SyntheticFixtureUser, ...]) -> None:
    contributor_task = next(item for item in synthetic_task_specs() if item.key == "mar-3")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO work_package_participants"
                "(package_id,user_id,role,active,created_at,ended_at) "
                "VALUES (:package_id,:user_id,'contributor',true,:created_at,NULL)"
            ),
            {
                "package_id": contributor_task.package_id(1),
                "user_id": synthetic_user_id("analyst@example.test"),
                "created_at": datetime(2026, 8, 3, tzinfo=UTC),
            },
        )
    personal_work = PostgresMyWorkStore(engine)
    analyst_work = personal_work.list_my_work(
        synthetic_user_id("analyst@example.test"),
        include_completed=False,
        column=None,
        cursor=None,
        limit=1,
    )
    assert len(analyst_work.cards) == 1
    assert analyst_work.next_cursor is not None
    next_work = personal_work.list_my_work(
        synthetic_user_id("analyst@example.test"),
        include_completed=False,
        column=None,
        cursor=analyst_work.next_cursor,
        limit=5,
    )
    assert len(next_work.cards) == 1
    assert {analyst_work.cards[0].ticket_id, next_work.cards[0].ticket_id} == {
        item.ticket_id for item in synthetic_task_specs() if item.key in {"mar-2", "mar-3"}
    }
    assert (
        personal_work.list_my_work(
            synthetic_user_id("customer.3@example.test"),
            include_completed=True,
            column=None,
            cursor=None,
            limit=5,
        ).cards
        == ()
    )
    _assert_forecast(engine, users)
    _assert_jioc_shadow_context(engine)


def _assert_forecast(engine: Engine, users: tuple[SyntheticFixtureUser, ...]) -> None:
    _project_accounts(engine, users)
    task = next(item for item in synthetic_task_specs() if item.key == "mar-2")
    unit_id = next(item.unit_id for item in synthetic_unit_specs() if item.key == task.unit_key)
    with engine.connect() as connection:
        grant_id = connection.execute(
            text(
                "SELECT grant_id FROM team_management_grants "
                "WHERE manager_user_id=:manager_id AND root_unit_id=:unit_id "
                "AND action='task:assign' AND revoked_at IS NULL LIMIT 1"
            ),
            {"manager_id": synthetic_user_id(task.manager_username), "unit_id": unit_id},
        ).scalar_one()
    forecast = PostgresTeamCapacityForecastStore(engine).forecast(
        synthetic_user_id(task.manager_username),
        unit_id,
        grant_id,
        datetime(2026, 8, 4, 8, tzinfo=UTC),
        datetime(2026, 8, 8, 18, tzinfo=UTC),
    )
    assert forecast.people_considered > 0
    assert forecast.people_included > 0
    assert forecast.assignable_minutes <= forecast.physical_minutes


def _project_accounts(engine: Engine, users: tuple[SyntheticFixtureUser, ...]) -> None:
    analyst_ids = {
        synthetic_user_id(item.username)
        for item in synthetic_posting_specs()
        if item.assignment_eligible or item.username.startswith("analyst")
    }
    with engine.begin() as connection:
        for user in users:
            connection.execute(
                text(
                    "INSERT INTO identity_account_projection"
                    "(user_id,is_active,roles,credential_version,source_hash) "
                    "VALUES (:user_id,:active,:roles,0,:source_hash)"
                ),
                {
                    "user_id": user.user_id,
                    "active": user.is_active,
                    "roles": ["Analyst"] if user.user_id in analyst_ids else [],
                    "source_hash": "0" * 64,
                },
            )


def _assert_jioc_shadow_context(engine: Engine) -> None:
    context = PostgresShadowRoutingOperationalContext(engine)
    snapshot = context.snapshot(
        object(),  # type: ignore[arg-type] - the bounded adapter admits no ticket fields
        ("RFA-MARITIME", "CM-GEO-LAND"),
    )
    assert snapshot.capability_catalogue_version == RELATIONAL_CONTEXT_VERSION
    assert snapshot.captured_at is not None
    assert snapshot.candidate_capacity[0].startswith("RFA-MARITIME:available:")
    assert snapshot.candidate_capacity[1].startswith("CM-GEO-LAND:available:")
