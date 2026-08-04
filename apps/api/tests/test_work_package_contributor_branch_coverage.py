"""Branch coverage for the reviewed contributor lifecycle boundary."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Connection, RowMapping

from coeus.api.work_package_contributor_contracts import call_contributor_change
from coeus.core.errors import AppError
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.work_package_contributors import (
    ChangeContributorCommand,
    ContributorChangePreview,
    ContributorChangeRequest,
    ContributorOperation,
    WorkPackageContributorConflict,
    WorkPackageContributorDenied,
    contributor_change_hash,
)
from coeus.persistence.work_package_contributors_postgres import (
    PostgresWorkPackageContributorStore,
    _load_and_validate,
    _validate_grant,
    _validate_leaf,
    _validate_package_scope,
)
from coeus.services.work_package_contributors import WorkPackageContributorService

NOW = datetime(2026, 8, 4, 8, tzinfo=UTC)


class _Result:
    def __init__(self, rows: tuple[Any, ...] = (), scalar: Any = None) -> None:
        self.rows, self.scalar = rows, scalar

    def mappings(self) -> "_Result":
        return self

    def first(self) -> Any:
        return self.rows[0] if self.rows else None

    def scalar_one(self) -> Any:
        return self.scalar

    def scalar_one_or_none(self) -> Any:
        return self.scalar

    def __iter__(self) -> Iterator[Any]:
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0)


def _request(**changes: object) -> ContributorChangeRequest:
    request = ContributorChangeRequest(
        uuid4(),
        uuid4(),
        uuid4(),
        ContributorOperation.ADD,
        1,
        2,
        uuid4(),
        3,
        uuid4(),
        4,
        5,
        "a" * 64,
    )
    return replace(request, **changes)  # type: ignore[arg-type]


def _command(request: ContributorChangeRequest | None = None) -> ChangeContributorCommand:
    request = request or _request()
    actor = uuid4()
    return ChangeContributorCommand(
        uuid4(), "contributor-branch", actor, request, contributor_change_hash(actor, request)
    )


def _package(request: ContributorChangeRequest, **changes: object) -> RowMapping:
    row: dict[str, object] = {
        "version": request.expected_package_version,
        "ownership_version": request.expected_ownership_version,
        "owning_unit_id": request.unit_id,
        "ownership_unit_id": request.unit_id,
        "ownership_state": "active",
        "accountable_user_id": uuid4(),
        "state": "ready",
    }
    row.update(changes)
    return cast(RowMapping, row)


def test_command_and_service_validation_and_delegation() -> None:
    request, actor = _request(), uuid4()
    with pytest.raises(ValueError, match="idempotency"):
        ChangeContributorCommand(uuid4(), "", actor, request, "a" * 64)
    with pytest.raises(ValueError, match="preview"):
        ChangeContributorCommand(uuid4(), "key", actor, request, "short")

    class Store:
        def preview(self, actor_id: UUID, value: ContributorChangeRequest) -> object:
            return actor_id, value

        def execute(self, command: ChangeContributorCommand) -> object:
            return command

    service = WorkPackageContributorService(cast(Any, Store()))
    assert service.preview(actor, request) == (actor, request)
    command = _command(request)
    assert service.execute(command) is command


def test_http_error_mappings_do_not_expose_denial_details() -> None:
    with pytest.raises(AppError) as conflict:
        call_contributor_change(
            lambda: (_ for _ in ()).throw(WorkPackageContributorConflict("changed"))
        )
    assert conflict.value.status_code == 409
    with pytest.raises(AppError) as invalid:
        call_contributor_change(lambda: (_ for _ in ()).throw(ValueError("invalid")))
    assert invalid.value.status_code == 422


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


class _Engine:
    def __init__(self, connection: _Transaction) -> None:
        self.connection = connection

    def connect(self) -> _Transaction:
        return self.connection


def test_execute_rejects_stale_preview_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    command, connection = _command(), _Transaction()
    store = PostgresWorkPackageContributorStore(cast(Any, _Engine(connection)))
    monkeypatch.setattr(
        "coeus.persistence.work_package_contributors_postgres._replay", lambda *_args: None
    )
    monkeypatch.setattr(
        "coeus.persistence.work_package_contributors_postgres._load_and_validate",
        lambda *_args, **_kwargs: (_package(command.request), False),
    )
    monkeypatch.setattr(
        "coeus.persistence.work_package_contributors_postgres._preview",
        lambda *_args: ContributorChangePreview(
            "b" * 64,
            command.request.package_id,
            1,
            2,
            command.request.contributor_user_id,
            False,
            2,
        ),
    )
    with pytest.raises(WorkPackageContributorConflict, match="no longer current"):
        store._execute_once(command)
    assert connection.closed


def test_load_and_package_scope_denials() -> None:
    request, actor = _request(), uuid4()
    with pytest.raises(WorkPackageContributorDenied, match="unavailable"):
        _load_and_validate(cast(Connection, _Connection(_Result())), actor, request, lock=False)
    with pytest.raises(WorkPackageContributorConflict, match="evidence changed"):
        _load_and_validate(
            cast(Connection, _Connection(_Result(rows=(_package(request, version=9),)))),
            actor,
            request,
            lock=True,
        )
    for changes in (
        {"owning_unit_id": uuid4()},
        {"ownership_unit_id": uuid4()},
        {"ownership_state": "cancelled"},
        {"state": "complete"},
    ):
        with pytest.raises(WorkPackageContributorDenied, match="outside"):
            _validate_package_scope(request, _package(request, **changes))
    with pytest.raises(WorkPackageContributorConflict, match="accountable"):
        _validate_package_scope(
            request, _package(request, accountable_user_id=request.contributor_user_id)
        )


@pytest.mark.parametrize(
    ("operation", "active", "message"),
    (
        (ContributorOperation.ADD, True, "already active"),
        (ContributorOperation.END, False, "not active"),
    ),
)
def test_load_rejects_duplicate_or_absent_participant(
    monkeypatch: pytest.MonkeyPatch,
    operation: ContributorOperation,
    active: bool,
    message: str,
) -> None:
    request, actor = _request(operation=operation), uuid4()
    monkeypatch.setattr(
        "coeus.persistence.work_package_contributors_postgres.transaction_time", lambda *_: NOW
    )
    for helper in (
        "_validate_leaf",
        "_validate_grant",
        "_validate_account_and_posting",
    ):
        monkeypatch.setattr(
            f"coeus.persistence.work_package_contributors_postgres.{helper}", lambda *_: None
        )
    monkeypatch.setattr(
        "coeus.persistence.work_package_contributors_postgres._participant_active",
        lambda *_: active,
    )
    with pytest.raises(WorkPackageContributorConflict, match=message):
        _load_and_validate(
            cast(Connection, _Connection(_Result(rows=(_package(request),)))),
            actor,
            request,
            lock=True,
        )


def test_leaf_and_grant_denials_and_exact_target(monkeypatch: pytest.MonkeyPatch) -> None:
    request, actor = _request(), uuid4()
    with pytest.raises(WorkPackageContributorDenied, match="leaf"):
        _validate_leaf(cast(Connection, _Connection(_Result())), request.unit_id, NOW)
    _validate_leaf(
        cast(Connection, _Connection(_Result(scalar=request.unit_id))), request.unit_id, NOW
    )
    with pytest.raises(WorkPackageContributorDenied, match="authority"):
        _validate_grant(cast(Connection, _Connection(_Result())), actor, request, NOW)
    grant = {
        "grant_id": request.authorising_grant_id,
        "root_unit_id": uuid4(),
        "version": request.expected_grant_version,
    }
    with pytest.raises(WorkPackageContributorDenied, match="authority"):
        _validate_grant(
            cast(Connection, _Connection(_Result(rows=({**grant, "version": 99},)))),
            actor,
            request,
            NOW,
        )

    def denied(*_args: object) -> None:
        raise OrganisationAuthorityDenied

    monkeypatch.setattr(
        "coeus.persistence.work_package_contributors_postgres.validate_lineage", denied
    )
    with pytest.raises(WorkPackageContributorDenied, match="authority"):
        _validate_grant(cast(Connection, _Connection(_Result(rows=(grant,)))), actor, request, NOW)
    targets: list[UUID] = []
    monkeypatch.setattr(
        "coeus.persistence.work_package_contributors_postgres.validate_lineage",
        lambda _c, _g, _a, target, _action, _at: targets.append(target),
    )
    _validate_grant(cast(Connection, _Connection(_Result(rows=(grant,)))), actor, request, NOW)
    assert targets == [request.unit_id]
