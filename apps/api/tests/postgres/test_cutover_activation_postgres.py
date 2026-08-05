"""Real PostgreSQL evidence for exact-candidate cutover activation."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverManifest,
    CutoverSlice,
    CutoverSliceStatus,
)
from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE
from coeus.persistence.cutover_activation_postgres import PostgresCutoverActivationStore

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 8, 4, 9, tzinfo=UTC)
EMPTY_HASH = sha256(b"[]").hexdigest()


def _manifest() -> CutoverManifest:
    return CutoverManifest(
        "abcdef123456",
        "20260804_0045",
        EMPTY_HASH,
        EMPTY_HASH,
        EMPTY_HASH,
        ROUTING_RELATIONAL_CAPACITY_RELEASE,
        "4" * 64,
        "ci-1234",
        "5" * 64,
        "6" * 64,
        "security-review-1234",
        "7" * 64,
        "8" * 64,
    )


def _migrate_and_seed(url: str) -> tuple[PostgresCutoverActivationStore, tuple[UUID, ...]]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    actors = tuple(uuid4() for _ in range(4))
    with engine.begin() as connection:
        for actor in actors:
            connection.execute(
                text(
                    "INSERT INTO identity_account_projection"
                    "(user_id,is_active,roles,credential_version,source_hash) "
                    "VALUES (:actor,true,ARRAY['Administrator'],1,:hash)"
                ),
                {"actor": actor, "hash": "a" * 64},
            )
    return PostgresCutoverActivationStore(engine), actors


def _approve_slice(
    store: PostgresCutoverActivationStore,
    slice: CutoverSlice,
    actors: tuple[UUID, ...],
    offset: int,
) -> tuple[UUID, UUID]:
    at = NOW + timedelta(minutes=offset)
    preview = store.preview(slice, _manifest(), actors[0], at)
    security = store.approve(
        slice,
        preview.candidate_hash,
        preview.preview_hash,
        CutoverApprovalRole.SECURITY_REVIEW,
        actors[1],
        at + timedelta(seconds=1),
    )
    release = store.approve(
        slice,
        preview.candidate_hash,
        preview.preview_hash,
        CutoverApprovalRole.RELEASE_AUTHORITY,
        actors[2],
        at + timedelta(seconds=2),
    )
    return security.approval_id, release.approval_id


def test_all_exact_candidate_slices_activate_and_bind_runtime_configuration(
    postgres_database_url: str,
) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    calendar_approvals = _approve_slice(store, CutoverSlice.CALENDAR, actors, 0)
    with pytest.raises(ValueError, match="predecessors"):
        store.execute(
            CutoverSlice.CALENDAR,
            _manifest().candidate_hash,
            calendar_approvals,
            actors[3],
            NOW + timedelta(seconds=3),
        )
    organisation_approvals = _approve_slice(store, CutoverSlice.ORGANISATION, actors, 1)
    executions = (
        (CutoverSlice.ORGANISATION, organisation_approvals, 1),
        (CutoverSlice.CALENDAR, calendar_approvals, 2),
        (
            CutoverSlice.TASK_CAPACITY,
            _approve_slice(store, CutoverSlice.TASK_CAPACITY, actors, 3),
            3,
        ),
    )
    for slice, approvals, offset in executions:
        result = store.execute(
            slice,
            _manifest().candidate_hash,
            approvals,
            actors[3],
            NOW + timedelta(minutes=offset, seconds=3),
        )
        assert result.status is CutoverSliceStatus.ACTIVE

    state = store.state()
    assert state.eligible
    assert {item.status for item in state.slices} == {CutoverSliceStatus.ACTIVE}
    assert store.active_candidate_is_eligible(
        _manifest().candidate_hash,
        _manifest().source_revision,
        ROUTING_RELATIONAL_CAPACITY_RELEASE,
    )
    assert not store.active_candidate_is_eligible(
        _manifest().candidate_hash, "different-revision", ROUTING_RELATIONAL_CAPACITY_RELEASE
    )
    assert not store.active_candidate_is_eligible(
        _manifest().candidate_hash, _manifest().source_revision, "different-release"
    )


def test_activation_failure_rolls_back_fence_checkpoint_and_state(
    postgres_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    approvals = _approve_slice(store, CutoverSlice.ORGANISATION, actors, 0)
    with pytest.raises(ValueError, match="not approved"):
        store.execute(
            CutoverSlice.ORGANISATION,
            _manifest().candidate_hash,
            approvals,
            actors[3],
            NOW + timedelta(minutes=16),
        )

    def interrupt(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("synthetic interruption")

    with monkeypatch.context() as context:
        context.setattr("coeus.persistence.cutover_activation_execution.record_evidence", interrupt)
        with pytest.raises(RuntimeError, match="interruption"):
            store.execute(
                CutoverSlice.ORGANISATION,
                _manifest().candidate_hash,
                approvals,
                actors[3],
                NOW + timedelta(seconds=3),
            )
    assert store.state().slices[0].status is CutoverSliceStatus.APPROVED
    with store._engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM organisation_cutover_writer_fences")
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM organisation_cutover_checkpoints")
            ).scalar_one()
            == 1
        )
    resumed = store.execute(
        CutoverSlice.ORGANISATION,
        _manifest().candidate_hash,
        approvals,
        actors[3],
        NOW + timedelta(minutes=6),
    )
    assert resumed.status is CutoverSliceStatus.ACTIVE
    with store._engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM organisation_cutover_recovery_events")
            ).scalar_one()
            == 1
        )
