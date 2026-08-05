"""Evidence guards a predecessor cancellation applies before it commits."""

from uuid import uuid4

import pytest
from package_lifecycle_support import lifecycle_fixture
from sqlalchemy import create_engine, text

from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    DependantDisposition,
    DependantDispositionAction,
    PredecessorCancellationConflict,
    PredecessorCancellationDenied,
    PredecessorCancellationRequest,
)
from coeus.persistence.package_predecessor_cancellation_postgres import (
    PostgresPredecessorCancellationStore,
)

pytestmark = pytest.mark.postgres


def _ready(engine: object, package_id: object) -> None:
    with engine.begin() as connection:  # type: ignore[attr-defined]
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET state='ready',remaining_minutes=120,version=2 "
                "WHERE package_id=:id"
            ),
            {"id": package_id},
        )


def _request(evidence: object, **overrides: object) -> PredecessorCancellationRequest:
    values: dict[str, object] = {
        "unit_id": evidence.unit_id,  # type: ignore[attr-defined]
        "package_id": evidence.predecessor_id,  # type: ignore[attr-defined]
        "expected_package_version": 2,
        "expected_ownership_version": 2,
        "authorising_grant_id": evidence.request.authorising_grant_id,  # type: ignore[attr-defined]
        "expected_grant_version": evidence.request.expected_grant_version,  # type: ignore[attr-defined]
        "dispositions": (
            DependantDisposition(
                evidence.package_id,  # type: ignore[attr-defined]
                1,
                DependantDispositionAction.UNLINK,
            ),
        ),
    }
    values.update(overrides)
    return PredecessorCancellationRequest(**values)  # type: ignore[arg-type]


def test_a_package_outside_the_named_unit_is_unavailable(postgres_database_url: str) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    _ready(engine, evidence.predecessor_id)
    store = PostgresPredecessorCancellationStore(engine)

    with pytest.raises(PredecessorCancellationDenied, match="work package is unavailable"):
        store.preview(evidence.actor_id, _request(evidence, unit_id=uuid4()))
    with pytest.raises(PredecessorCancellationDenied, match="work package is unavailable"):
        store.preview(evidence.actor_id, _request(evidence, package_id=uuid4()))
    engine.dispose()


@pytest.mark.parametrize(
    "overrides",
    [{"expected_package_version": 9}, {"expected_ownership_version": 9}],
)
def test_stale_package_or_ownership_evidence_is_a_conflict(
    postgres_database_url: str, overrides: dict[str, object]
) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    _ready(engine, evidence.predecessor_id)
    store = PostgresPredecessorCancellationStore(engine)

    with pytest.raises(PredecessorCancellationConflict, match="work package evidence changed"):
        store.preview(evidence.actor_id, _request(evidence, **overrides))
    engine.dispose()


@pytest.mark.parametrize("state", ["complete", "cancelled"])
def test_a_terminal_package_cannot_be_cancelled_again(
    postgres_database_url: str, state: str
) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET state=:state,remaining_minutes=0,version=2 "
                "WHERE package_id=:id"
            ),
            {"state": state, "id": evidence.predecessor_id},
        )
    store = PostgresPredecessorCancellationStore(engine)

    with pytest.raises(PredecessorCancellationConflict, match="already terminal"):
        store.preview(evidence.actor_id, _request(evidence))
    engine.dispose()


def test_a_closed_ownership_makes_the_package_unavailable(postgres_database_url: str) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    _ready(engine, evidence.predecessor_id)
    with engine.begin() as connection:
        # A cancelled ownership carries no acceptance timestamp.
        connection.execute(
            text("UPDATE team_task_ownership SET state='cancelled',accepted_at=NULL,version=2")
        )
    store = PostgresPredecessorCancellationStore(engine)

    with pytest.raises(PredecessorCancellationDenied, match="work package is unavailable"):
        store.preview(evidence.actor_id, _request(evidence))
    engine.dispose()


def test_a_missing_or_stale_grant_refuses_the_cancellation(postgres_database_url: str) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    _ready(engine, evidence.predecessor_id)
    store = PostgresPredecessorCancellationStore(engine)

    with pytest.raises(PredecessorCancellationDenied, match="task assignment authority"):
        store.preview(evidence.actor_id, _request(evidence, authorising_grant_id=uuid4()))
    with pytest.raises(PredecessorCancellationDenied, match="task assignment authority"):
        store.preview(evidence.actor_id, _request(evidence, expected_grant_version=9))
    with pytest.raises(PredecessorCancellationDenied, match="task assignment authority"):
        store.preview(uuid4(), _request(evidence))
    engine.dispose()


def test_a_superseded_preview_cannot_be_executed(postgres_database_url: str) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    _ready(engine, evidence.predecessor_id)
    store = PostgresPredecessorCancellationStore(engine)
    request = _request(evidence)

    with pytest.raises(PredecessorCancellationConflict, match="no longer current"):
        store.execute(
            CancelPredecessorCommand(uuid4(), "cancel-1", evidence.actor_id, request, "a" * 64)
        )
    engine.dispose()


def test_an_executed_cancellation_replays_its_recorded_result(
    postgres_database_url: str,
) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    _ready(engine, evidence.predecessor_id)
    store = PostgresPredecessorCancellationStore(engine)
    request = _request(evidence)
    preview = store.preview(evidence.actor_id, request)
    command = CancelPredecessorCommand(
        uuid4(), "cancel-replay", evidence.actor_id, request, preview.preview_hash
    )

    first = store.execute(command)
    replayed = store.execute(command)

    assert not first.replayed and replayed.replayed
    assert first.package_version == replayed.package_version
    engine.dispose()
