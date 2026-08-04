"""Branch coverage for reviewed dependency commands."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangePreview,
    DependencyChangeRequest,
    DependencyOperation,
    WorkPackageDependencyConflict,
    WorkPackageDependencyDenied,
    dependency_change_hash,
)
from coeus.persistence.work_package_dependencies_postgres import (
    PostgresWorkPackageDependencyStore,
    _load_and_validate,
    _replay,
    _validate_graph,
    _validate_leaf_and_grant,
    _validate_scope_and_versions,
)

NOW = datetime(2026, 8, 4, 8, tzinfo=UTC)


class _Result:
    def __init__(self, rows: tuple[Any, ...] = (), scalar: Any = None) -> None:
        self.rows, self.scalar = rows, scalar

    def mappings(self) -> "_Result":
        return self

    def first(self) -> Any:
        return self.rows[0] if self.rows else None

    def one(self) -> Any:
        return self.rows[0]

    def scalar_one_or_none(self) -> Any:
        return self.scalar

    def __iter__(self) -> Iterator[Any]:
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0)


def _request(**changes: object) -> DependencyChangeRequest:
    request = DependencyChangeRequest(
        uuid4(), uuid4(), uuid4(), DependencyOperation.ADD, 1, 2, 3, uuid4(), 4
    )
    return replace(request, **changes)  # type: ignore[arg-type]


def _row(request: DependencyChangeRequest, package_id: UUID, **changes: object) -> RowMapping:
    row: dict[str, object] = {
        "package_id": package_id,
        "ticket_id": uuid4(),
        "workflow_leg": "rfa",
        "owning_unit_id": request.unit_id,
        "ownership_unit_id": request.unit_id,
        "ownership_state": "active",
        "ownership_version": request.expected_ownership_version,
        "state": "ready",
        "version": (
            request.expected_package_version
            if package_id == request.package_id
            else request.expected_predecessor_version
        ),
    }
    row.update(changes)
    return cast(RowMapping, row)


def _rows(request: DependencyChangeRequest) -> tuple[RowMapping, RowMapping]:
    ticket_id = uuid4()
    return (
        _row(request, request.package_id, ticket_id=ticket_id),
        _row(request, request.predecessor_package_id, ticket_id=ticket_id),
    )


@pytest.mark.parametrize(
    "changes",
    (
        {"version": 99},
        {"ownership_version": 99},
    ),
)
def test_scope_rejects_stale_target_evidence(changes: dict[str, object]) -> None:
    request = _request()
    package, predecessor = _rows(request)
    with pytest.raises(WorkPackageDependencyConflict, match="evidence"):
        _validate_scope_and_versions(request, cast(RowMapping, {**package, **changes}), predecessor)


def test_scope_rejects_stale_predecessor_and_cross_scope() -> None:
    request = _request()
    package, predecessor = _rows(request)
    with pytest.raises(WorkPackageDependencyConflict, match="evidence"):
        _validate_scope_and_versions(
            request, package, cast(RowMapping, {**predecessor, "version": 99})
        )
    with pytest.raises(WorkPackageDependencyDenied, match="same task"):
        _validate_scope_and_versions(
            request, package, cast(RowMapping, {**predecessor, "ticket_id": uuid4()})
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"owning_unit_id": uuid4()}, "same task"),
        ({"ownership_unit_id": uuid4()}, "active assignment"),
        ({"ownership_state": "ended"}, "active assignment"),
        ({"state": "complete"}, "active assignment"),
    ),
)
def test_scope_rejects_inactive_target(changes: dict[str, object], message: str) -> None:
    request = _request()
    package, predecessor = _rows(request)
    with pytest.raises(WorkPackageDependencyDenied, match=message):
        _validate_scope_and_versions(request, cast(RowMapping, {**package, **changes}), predecessor)


def test_leaf_and_grant_fail_closed_and_validate_exact_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, actor = _request(), uuid4()
    with pytest.raises(WorkPackageDependencyDenied, match="leaf"):
        _validate_leaf_and_grant(cast(Connection, _Connection(_Result())), actor, request, NOW)
    with pytest.raises(WorkPackageDependencyDenied, match="authority"):
        _validate_leaf_and_grant(
            cast(Connection, _Connection(_Result(scalar=request.unit_id), _Result())),
            actor,
            request,
            NOW,
        )
    grant = {"grant_id": request.authorising_grant_id, "version": 99}
    with pytest.raises(WorkPackageDependencyDenied, match="authority"):
        _validate_leaf_and_grant(
            cast(
                Connection,
                _Connection(_Result(scalar=request.unit_id), _Result(rows=(grant,))),
            ),
            actor,
            request,
            NOW,
        )

    def denied(*_args: object) -> None:
        raise OrganisationAuthorityDenied

    grant["version"] = request.expected_grant_version
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres.validate_lineage", denied
    )
    with pytest.raises(WorkPackageDependencyDenied, match="authority"):
        _validate_leaf_and_grant(
            cast(
                Connection,
                _Connection(_Result(scalar=request.unit_id), _Result(rows=(grant,))),
            ),
            actor,
            request,
            NOW,
        )
    targets: list[UUID] = []
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres.validate_lineage",
        lambda _c, _g, _a, target, _action, _at: targets.append(target),
    )
    _validate_leaf_and_grant(
        cast(
            Connection,
            _Connection(_Result(scalar=request.unit_id), _Result(rows=(grant,))),
        ),
        actor,
        request,
        NOW,
    )
    assert targets == [request.unit_id]


@pytest.mark.parametrize(
    ("operation", "active", "message"),
    (
        (DependencyOperation.ADD, True, "already exists"),
        (DependencyOperation.REMOVE, False, "does not exist"),
    ),
)
def test_load_rejects_duplicate_or_missing_edge(
    monkeypatch: pytest.MonkeyPatch,
    operation: DependencyOperation,
    active: bool,
    message: str,
) -> None:
    request = _request(operation=operation)
    rows = _rows(request)
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres.transaction_time", lambda *_: NOW
    )
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres._validate_leaf_and_grant",
        lambda *_: None,
    )
    connection = _Connection(_Result(rows=rows), _Result(scalar=1 if active else None))
    with pytest.raises(WorkPackageDependencyConflict, match=message):
        _load_and_validate(cast(Connection, connection), uuid4(), request, lock=True)


def test_load_denies_missing_package() -> None:
    request = _request()
    with pytest.raises(WorkPackageDependencyDenied, match="unavailable"):
        _load_and_validate(
            cast(Connection, _Connection(_Result(rows=(_rows(request)[0],)))),
            uuid4(),
            request,
            lock=False,
        )


def test_graph_applies_add_and_remove_before_oracle() -> None:
    request = _request()
    package_row = {"ticket_id": uuid4(), "workflow_leg": "rfa"}
    _validate_graph(
        cast(
            Connection,
            _Connection(
                _Result(rows=(package_row,)),
                _Result(rows=((request.package_id,), (request.predecessor_package_id,))),
                _Result(),
            ),
        ),
        request,
        lock=False,
    )
    _validate_graph(
        cast(
            Connection,
            _Connection(
                _Result(rows=(package_row,)),
                _Result(rows=((request.package_id,), (request.predecessor_package_id,))),
                _Result(rows=((request.package_id, request.predecessor_package_id),)),
            ),
        ),
        replace(request, operation=DependencyOperation.REMOVE),
        lock=True,
    )


def test_replay_accepts_exact_identity_and_rejects_conflicts() -> None:
    request, actor = _request(), uuid4()
    command = ChangeDependencyCommand(
        uuid4(), "dependency-branch", actor, request, dependency_change_hash(actor, request)
    )
    assert _replay(cast(Connection, _Connection(_Result())), command) is None
    row = {
        "request_hash": dependency_change_hash(actor, request),
        "actor_user_id": actor,
        "package_id": request.package_id,
        "predecessor_package_id": request.predecessor_package_id,
        "operation": request.operation.value,
        "result_package_version": 2,
        "result_active": True,
    }
    replay = _replay(cast(Connection, _Connection(_Result(rows=(row,)))), command)
    assert replay is not None and replay.replayed
    with pytest.raises(WorkPackageDependencyConflict, match="identities"):
        _replay(cast(Connection, _Connection(_Result(rows=(row, row)))), command)
    with pytest.raises(WorkPackageDependencyConflict, match="reused"):
        _replay(
            cast(Connection, _Connection(_Result(rows=({**row, "actor_user_id": uuid4()},)))),
            command,
        )


class _Transaction:
    closed = False

    def execution_options(self, **_kwargs: object) -> "_Transaction":
        return self

    def begin(self) -> "_Transaction":
        return self

    def __enter__(self) -> "_Transaction":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_execute_rejects_stale_preview_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    request, actor, connection = _request(), uuid4(), _Transaction()
    command = ChangeDependencyCommand(
        uuid4(), "dependency-stale", actor, request, dependency_change_hash(actor, request)
    )
    store = PostgresWorkPackageDependencyStore(
        cast(Any, type("E", (), {"connect": lambda _: connection})())
    )
    package, predecessor = _rows(request)
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres._replay", lambda *_: None
    )
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres._load_and_validate",
        lambda *_args, **_kwargs: (package, predecessor, False),
    )
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres._preview",
        lambda *_: DependencyChangePreview(
            "f" * 64, request.package_id, 1, request.predecessor_package_id, 2, 3, False, 2
        ),
    )
    with pytest.raises(WorkPackageDependencyConflict, match="no longer current"):
        store._execute_once(command)
    assert connection.closed
