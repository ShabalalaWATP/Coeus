"""Branch coverage for package planning and aggregate capacity forecasts."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.work_package_planning import (
    PlanWorkPackageCommand,
    WorkPackagePlanningConflict,
    WorkPackagePlanningDenied,
    WorkPackagePlanningPreview,
    WorkPackagePlanRequest,
    planning_hash,
)
from coeus.persistence.work_package_planning_postgres import (
    PostgresWorkPackagePlanningStore,
    _load_and_validate,
    _replay,
    _validate_current_scope,
)
from coeus.services.work_package_planning import WorkPackagePlanningService

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

    def __iter__(self) -> Iterator[Any]:
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0)


def _request(**changes: object) -> WorkPackagePlanRequest:
    request = WorkPackagePlanRequest(
        uuid4(),
        uuid4(),
        1,
        2,
        uuid4(),
        240,
        180,
        NOW + timedelta(days=1),
        2,
        "Synthetic priority.",
        uuid4(),
        NOW,
        NOW + timedelta(hours=4),
        60,
        uuid4(),
    )
    return replace(request, **changes)  # type: ignore[arg-type]


def _command(request: WorkPackagePlanRequest | None = None) -> PlanWorkPackageCommand:
    request = request or _request()
    return PlanWorkPackageCommand(
        uuid4(), "plan-branch-test", uuid4(), request, planning_hash(uuid4(), request)
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"expected_package_version": 0}, "versions"),
        ({"reserved_minutes": 195}, "reserved effort cannot exceed"),
        ({"priority_override_reason": "x" * 501}, "reason"),
        ({"due_at": NOW.replace(tzinfo=None)}, "timezone-aware"),
    ),
)
def test_planning_domain_remaining_validation_branches(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _request(**changes)


def test_planning_command_identity_validation_branches() -> None:
    request = _request()
    actor = uuid4()
    with pytest.raises(ValueError, match="idempotency"):
        PlanWorkPackageCommand(uuid4(), "", actor, request, planning_hash(actor, request))
    with pytest.raises(ValueError, match="preview"):
        PlanWorkPackageCommand(uuid4(), "valid", actor, request, "short")


class _PlanningStore:
    def __init__(self, preview: WorkPackagePlanningPreview) -> None:
        self.preview_result = preview
        self.preview_call: tuple[UUID, WorkPackagePlanRequest] | None = None
        self.command: PlanWorkPackageCommand | None = None

    def preview(self, actor: UUID, request: WorkPackagePlanRequest) -> WorkPackagePlanningPreview:
        self.preview_call = actor, request
        return self.preview_result

    def execute(self, command: PlanWorkPackageCommand) -> Any:
        self.command = command
        return "executed"


def test_package_planning_service_delegates_without_changing_authority() -> None:
    request, actor = _request(), uuid4()
    preview = WorkPackagePlanningPreview(
        "a" * 64, request.package_id, 1, 2, request.accountable_user_id, 2
    )
    store = _PlanningStore(preview)
    service = WorkPackagePlanningService(store)
    assert service.preview(actor, request) is preview
    command = PlanWorkPackageCommand(uuid4(), "key", actor, request, "a" * 64)
    assert cast(Any, service.execute(command)) == "executed"
    assert store.preview_call == (actor, request) and store.command is command


class _TransactionalConnection:
    def __init__(self) -> None:
        self.closed = False

    def execution_options(self, **_kwargs: object) -> "_TransactionalConnection":
        return self

    def begin(self) -> "_TransactionalConnection":
        return self

    def __enter__(self) -> "_TransactionalConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class _Engine:
    def __init__(self, connection: _TransactionalConnection) -> None:
        self.connection = connection

    def connect(self) -> _TransactionalConnection:
        return self.connection


def test_execute_rejects_a_stale_preview_and_closes_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = _command()
    connection = _TransactionalConnection()
    store = PostgresWorkPackagePlanningStore(cast(Any, _Engine(connection)))
    monkeypatch.setattr(
        "coeus.persistence.work_package_planning_postgres._replay", lambda *_args: None
    )
    monkeypatch.setattr(
        "coeus.persistence.work_package_planning_postgres._load_and_validate",
        lambda *_args, **_kwargs: (_package_row(command.request), _account_row(command.request)),
    )
    monkeypatch.setattr(
        "coeus.persistence.work_package_planning_postgres._preview",
        lambda *_args: WorkPackagePlanningPreview(
            "b" * 64,
            command.request.package_id,
            1,
            2,
            command.request.accountable_user_id,
            2,
        ),
    )
    with pytest.raises(WorkPackagePlanningConflict, match="no longer current"):
        store._execute_once(command)
    assert connection.closed


def _package_row(request: WorkPackagePlanRequest, **changes: object) -> RowMapping:
    row: dict[str, object] = {
        "version": request.expected_package_version,
        "ownership_version": request.expected_ownership_version,
        "owning_unit_id": request.unit_id,
        "ownership_unit_id": request.unit_id,
        "ownership_state": "active",
        "accountable_user_id": request.accountable_user_id,
        "state": "pending",
    }
    row.update(changes)
    return cast(RowMapping, row)


def _account_row(request: WorkPackagePlanRequest, **changes: object) -> RowMapping:
    row: dict[str, object] = {
        "user_id": request.accountable_user_id,
        "is_active": True,
        "roles": ["Analyst"],
        "credential_version": 0,
        "source_hash": "a" * 64,
    }
    row.update(changes)
    return cast(RowMapping, row)


def test_package_load_rejects_missing_and_stale_rows() -> None:
    request, actor = _request(), uuid4()
    with pytest.raises(WorkPackagePlanningDenied, match="unavailable"):
        _load_and_validate(cast(Connection, _Connection(_Result())), actor, request, lock=False)
    stale = _package_row(request, version=99)
    with pytest.raises(WorkPackagePlanningConflict, match="evidence changed"):
        _load_and_validate(
            cast(Connection, _Connection(_Result(rows=(stale,)))), actor, request, lock=True
        )


def test_package_scope_rejects_scope_grant_lineage_and_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, actor = _request(), uuid4()
    with pytest.raises(WorkPackagePlanningDenied, match="outside"):
        _validate_current_scope(
            cast(Connection, _Connection()), actor, request, _package_row(request, state="complete")
        )
    with pytest.raises(WorkPackagePlanningDenied, match="authority"):
        _validate_current_scope(
            cast(
                Connection,
                _Connection(_Result(scalar=NOW), _Result(rows=(_account_row(request),)), _Result()),
            ),
            actor,
            request,
            _package_row(request),
        )
    with pytest.raises(WorkPackagePlanningDenied, match="account"):
        _validate_current_scope(
            cast(Connection, _Connection(_Result(scalar=NOW), _Result())),
            actor,
            request,
            _package_row(request),
        )

    def denied(*_args: object) -> None:
        raise OrganisationAuthorityDenied

    monkeypatch.setattr("coeus.persistence.work_package_planning_postgres.validate_lineage", denied)
    grant = {"grant_id": request.authorising_grant_id, "root_unit_id": request.unit_id}
    with pytest.raises(WorkPackagePlanningDenied, match="authority"):
        _validate_current_scope(
            cast(
                Connection,
                _Connection(
                    _Result(scalar=NOW),
                    _Result(rows=(_account_row(request),)),
                    _Result(rows=(grant,)),
                ),
            ),
            actor,
            request,
            _package_row(request),
        )
    monkeypatch.setattr(
        "coeus.persistence.work_package_planning_postgres.validate_lineage", lambda *_args: None
    )
    with pytest.raises(WorkPackagePlanningDenied, match="full interval"):
        _validate_current_scope(
            cast(
                Connection,
                _Connection(
                    _Result(scalar=NOW),
                    _Result(rows=(_account_row(request),)),
                    _Result(rows=(grant,)),
                    _Result(rows=()),
                ),
            ),
            actor,
            request,
            _package_row(request),
        )


def _stored_command(command: PlanWorkPackageCommand, **changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "request_hash": planning_hash(command.actor_user_id, command.request),
        "actor_user_id": command.actor_user_id,
        "package_id": command.request.package_id,
        "operation": "update",
        "result_version": 2,
    }
    row.update(changes)
    return row


def test_planning_replay_rejects_collisions_and_missing_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = _command()
    assert _replay(cast(Connection, _Connection(_Result())), command) is None
    duplicate = _stored_command(command)
    with pytest.raises(WorkPackagePlanningConflict, match="identities"):
        _replay(cast(Connection, _Connection(_Result(rows=(duplicate, duplicate)))), command)
    with pytest.raises(WorkPackagePlanningConflict, match="identity was reused"):
        _replay(
            cast(
                Connection,
                _Connection(_Result(rows=(_stored_command(command, operation="assign"),))),
            ),
            command,
        )
    with pytest.raises(WorkPackagePlanningDenied, match="unavailable"):
        _replay(cast(Connection, _Connection(_Result(rows=(duplicate,)), _Result())), command)
    monkeypatch.setattr(
        "coeus.persistence.work_package_planning_postgres._validate_current_scope",
        lambda *_args: _account_row(command.request),
    )
    with pytest.raises(WorkPackagePlanningConflict, match="reservation evidence"):
        _replay(
            cast(
                Connection,
                _Connection(
                    _Result(rows=(duplicate,)),
                    _Result(rows=(_package_row(command.request),)),
                    _Result(),
                ),
            ),
            command,
        )
