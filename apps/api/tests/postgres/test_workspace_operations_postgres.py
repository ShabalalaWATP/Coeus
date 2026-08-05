"""Real PostgreSQL proof for integrated workspace operations authority."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from workspace_operations_support import (
    seed_authority,
    seed_delivery_profile,
    seed_membership,
    seed_store_link,
    seed_work_package,
)

from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.workspace_operations import (
    WorkspaceCommand,
    WorkspaceOperationsConflict,
    WorkspaceOperationsDenied,
    WorkspaceScope,
)
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.workspace_operations_postgres import PostgresWorkspaceOperationsStore

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres

ALL_ACTIONS = (
    "workspace:view",
    "workspace:configure",
    "workspace:export",
    "roster:view",
    "task:view",
)


def _bootstrap(database_url: str) -> tuple[Engine, UUID, UUID, dict[str, UUID]]:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    actor, bootstrap_actor, root_id = uuid4(), uuid4(), uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), bootstrap_actor, root_id, "Synthetic Team", "SYN", "Europe/London", ""
        )
    )
    activate_principals(engine, actor, bootstrap_actor)
    grants = seed_authority(engine, actor, root_id, ALL_ACTIONS)
    return engine, actor, root_id, grants


def _command(actor: UUID, operation: str, payload: dict[str, object]) -> WorkspaceCommand:
    return WorkspaceCommand(uuid4(), str(uuid4()), actor, operation, payload)


def _policy_payload(unit_id: UUID, grant_id: UUID, **overrides: object) -> dict[str, object]:
    return {
        "unit_id": unit_id,
        "authorising_grant_id": grant_id,
        "expected_grant_version": 1,
        "expected_version": 0,
        "expected_delivery_policy_version": 1,
        "wip_limit": 9,
        "service_target_hours": 48,
        "planning_cadence": "weekly",
        "planning_weekday": 2,
        "planning_local_time": "09:30",
        "planning_duration_minutes": 45,
        **overrides,
    }


def test_workspace_reads_are_scoped_and_policy_writes_are_replayable(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, grants = _bootstrap(postgres_database_url)
    seed_delivery_profile(engine, root_id, ("regional-analysis",))
    seed_membership(engine, actor, root_id)
    store = PostgresWorkspaceOperationsStore(engine)

    overview = store.overview(actor, root_id, WorkspaceScope.DIRECT)
    assert overview.unit_id == root_id
    assert overview.descendant_units == 0
    assert not overview.suppressed
    assert {metric.key for metric in overview.metrics}

    people = store.people(actor, root_id, WorkspaceScope.DIRECT)
    assert tuple(item.user_id for item in people) == (actor,)

    coverage = store.capabilities(actor, root_id, WorkspaceScope.DIRECT)
    assert tuple(item.capability_id for item in coverage) == ("regional-analysis",)
    assert coverage[0].gap is True

    # A descendant read of a small cohort must hide the exact counts.
    suppressed = store.capabilities(actor, root_id, WorkspaceScope.DESCENDANTS)
    assert suppressed[0].display == "<5" and suppressed[0].suppressed

    saved = store.save_policy(
        _command(
            actor, "save_workspace_policy", _policy_payload(root_id, grants["workspace:configure"])
        )
    )
    assert saved.wip_limit == 9 and saved.version == 1
    assert store.policy(actor, root_id).planning_duration_minutes == 45
    engine.dispose()


def test_policy_writes_refuse_stale_versions_and_mismatched_grants(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, grants = _bootstrap(postgres_database_url)
    seed_delivery_profile(engine, root_id, ())
    store = PostgresWorkspaceOperationsStore(engine)
    grant_id = grants["workspace:configure"]

    with pytest.raises(WorkspaceOperationsDenied):
        store.save_policy(
            _command(
                actor,
                "save_workspace_policy",
                _policy_payload(root_id, uuid4()),
            )
        )
    with pytest.raises(WorkspaceOperationsDenied):
        store.save_policy(
            _command(
                actor,
                "save_workspace_policy",
                _policy_payload(root_id, grant_id, expected_grant_version=9),
            )
        )
    with pytest.raises(WorkspaceOperationsConflict, match="policy version changed"):
        store.save_policy(
            _command(
                actor,
                "save_workspace_policy",
                _policy_payload(root_id, grant_id, expected_version=7),
            )
        )
    with pytest.raises(WorkspaceOperationsConflict, match="delivery policy version changed"):
        store.save_policy(
            _command(
                actor,
                "save_workspace_policy",
                _policy_payload(root_id, grant_id, expected_delivery_policy_version=9),
            )
        )

    replayed = _command(actor, "save_workspace_policy", _policy_payload(root_id, grant_id))
    first = store.save_policy(replayed)
    again = store.save_policy(replayed)
    assert first == again
    engine.dispose()


def test_search_widens_with_authority_and_stays_bounded(postgres_database_url: str) -> None:
    engine, actor, root_id, _ = _bootstrap(postgres_database_url)
    seed_membership(engine, actor, root_id)
    seed_work_package(engine, root_id, "Synthetic maritime assessment")
    seed_store_link(engine, actor, root_id, "Synthetic maritime report")
    store = PostgresWorkspaceOperationsStore(engine)

    results = store.search(actor, root_id, WorkspaceScope.DIRECT, "Synthetic", 20)
    kinds = {item.result_type for item in results}
    assert "team" in kinds
    assert "person" in kinds
    assert {"work_package", "store_product"} & kinds

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE team_management_grants SET revoked_at=now() "
                "WHERE manager_user_id=:actor AND action<>'workspace:view'"
            ),
            {"actor": actor},
        )
    narrowed = store.search(actor, root_id, WorkspaceScope.DIRECT, "Synthetic", 20)
    assert {item.result_type for item in narrowed} == {"team"}
    engine.dispose()


def test_exports_are_pinned_bounded_and_rechecked_at_download(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, grants = _bootstrap(postgres_database_url)
    seed_delivery_profile(engine, root_id, ())
    seed_membership(engine, actor, root_id)
    store = PostgresWorkspaceOperationsStore(engine)
    export_grant = grants["workspace:export"]

    def export_command() -> WorkspaceCommand:
        return _command(
            actor,
            "create_workspace_export",
            {
                "unit_id": root_id,
                "export_id": uuid4(),
                "include_descendants": False,
                "authorising_grant_id": export_grant,
                "expected_grant_version": 1,
                "format": "csv",
            },
        )

    created = store.create_export(export_command())
    assert created.state == "ready" and created.row_count
    assert store.get_export(actor, created.export_id) == created

    replay = export_command()
    assert store.create_export(replay) == store.create_export(replay)

    content = store.export_csv(actor, created.export_id)
    assert content.startswith(b"\xef\xbb\xbf")
    assert b"ISTARI TEAM OPERATIONAL EXPORT" in content
    assert b"SYNTHETIC EXERCISE" in content

    # Another actor never sees the pinned snapshot, and an expired job is gone.
    with pytest.raises(WorkspaceOperationsDenied):
        store.get_export(uuid4(), created.export_id)
    expired = datetime.now(UTC) - timedelta(hours=2)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE workspace_export_jobs SET created_at=:then,expires_at=:expires "
                "WHERE export_id=:export"
            ),
            {
                "then": expired,
                "expires": expired + timedelta(minutes=1),
                "export": created.export_id,
            },
        )
    with pytest.raises(WorkspaceOperationsDenied):
        store.get_export(actor, created.export_id)
    engine.dispose()


def test_exports_stop_at_the_hourly_limit(postgres_database_url: str) -> None:
    engine, actor, root_id, grants = _bootstrap(postgres_database_url)
    seed_delivery_profile(engine, root_id, ())
    store = PostgresWorkspaceOperationsStore(engine)

    for _ in range(5):
        store.create_export(
            _command(
                actor,
                "create_workspace_export",
                {
                    "unit_id": root_id,
                    "export_id": uuid4(),
                    "include_descendants": False,
                    "authorising_grant_id": grants["workspace:export"],
                    "expected_grant_version": 1,
                    "format": "csv",
                },
            )
        )

    with pytest.raises(WorkspaceOperationsConflict, match="hourly limit"):
        store.create_export(
            _command(
                actor,
                "create_workspace_export",
                {
                    "unit_id": root_id,
                    "export_id": uuid4(),
                    "include_descendants": False,
                    "authorising_grant_id": grants["workspace:export"],
                    "expected_grant_version": 1,
                    "format": "csv",
                },
            )
        )
    engine.dispose()


def test_every_read_fails_closed_for_a_suspended_or_ungranted_actor(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, _ = _bootstrap(postgres_database_url)
    seed_delivery_profile(engine, root_id, ())
    store = PostgresWorkspaceOperationsStore(engine)
    stranger = uuid4()

    for call in (
        lambda who: store.overview(who, root_id, WorkspaceScope.DIRECT),
        lambda who: store.people(who, root_id, WorkspaceScope.DIRECT),
        lambda who: store.capabilities(who, root_id, WorkspaceScope.DIRECT),
        lambda who: store.policy(who, root_id),
        lambda who: store.analytics(who, root_id, WorkspaceScope.DIRECT),
        lambda who: store.search(who, root_id, WorkspaceScope.DIRECT, "Synthetic", 20),
    ):
        with pytest.raises(WorkspaceOperationsDenied):
            call(stranger)

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:actor"),
            {"actor": actor},
        )
    with pytest.raises(WorkspaceOperationsDenied):
        store.overview(actor, root_id, WorkspaceScope.DIRECT)

    # An unknown unit is refused even when the actor holds the action.
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=true WHERE user_id=:actor"),
            {"actor": actor},
        )
    with pytest.raises(WorkspaceOperationsDenied):
        store.overview(actor, uuid4(), WorkspaceScope.DIRECT)
    engine.dispose()
