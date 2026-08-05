"""Evidence and application branch coverage for dependency commands."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy.engine import Connection

from coeus.api.work_package_dependency_contracts import (
    dependency_command,
    dependency_request,
    dependency_result,
)
from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangeRequest,
    DependencyChangeResult,
    DependencyOperation,
    dependency_change_hash,
)
from coeus.persistence.work_package_dependencies_postgres import _apply
from coeus.persistence.work_package_dependency_evidence import (
    append_dependency_evidence,
    dependency_history_values,
)
from coeus.persistence.work_package_dependency_schema import (
    work_package_dependency_schema_statements,
)
from coeus.schemas.work_package_dependencies import (
    ChangeDependencyCommandPayload,
    DependencyChangePayload,
)

NOW = datetime(2026, 8, 4, 9, tzinfo=UTC)


class _Result:
    def __init__(self, scalar: object = None) -> None:
        self.scalar = scalar

    def scalar_one(self) -> object:
        return self.scalar


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)
        self.calls: list[tuple[object, object]] = []

    def execute(self, statement: object, values: object = None) -> _Result:
        self.calls.append((statement, values))
        return self.results.pop(0) if self.results else _Result()


def _request(operation: DependencyOperation = DependencyOperation.ADD) -> DependencyChangeRequest:
    return DependencyChangeRequest(uuid4(), uuid4(), uuid4(), operation, 1, 2, 3, uuid4(), 4)


def _command(operation: DependencyOperation = DependencyOperation.ADD) -> ChangeDependencyCommand:
    request, actor = _request(operation), uuid4()
    return ChangeDependencyCommand(
        uuid4(),
        f"dependency-{operation.value}",
        actor,
        request,
        dependency_change_hash(actor, request),
    )


def test_schema_and_evidence_are_complete_and_operation_specific() -> None:
    statements = work_package_dependency_schema_statements()
    assert len(statements) == 4
    for operation, suffix in (
        (DependencyOperation.ADD, "added"),
        (DependencyOperation.REMOVE, "removed"),
    ):
        command = _command(operation)
        history = dependency_history_values(command, 2, NOW)
        assert history["event_type"] == f"dependency_{suffix}"
        connection = _Connection()
        append_dependency_evidence(cast(Connection, connection), command, 2, NOW)
        assert len(connection.calls) == 2


def test_apply_adds_and_removes_with_atomic_evidence(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres.transaction_time", lambda *_: NOW
    )
    evidence: list[tuple[DependencyOperation, int]] = []
    monkeypatch.setattr(
        "coeus.persistence.work_package_dependencies_postgres.append_dependency_evidence",
        lambda _c, command, version, _at: evidence.append((command.request.operation, version)),
    )
    for operation, expected_active in (
        (DependencyOperation.ADD, True),
        (DependencyOperation.REMOVE, False),
    ):
        connection = _Connection(_Result(2))
        result = _apply(cast(Connection, connection), _command(operation))
        assert (result.package_version, result.dependency_active) == (2, expected_active)
        assert len(connection.calls) == 4
    assert evidence == [(DependencyOperation.ADD, 2), (DependencyOperation.REMOVE, 2)]


def test_http_contract_builders_preserve_exact_command_evidence() -> None:
    request = _request()
    payload = DependencyChangePayload(
        predecessorPackageId=request.predecessor_package_id,
        operation=request.operation,
        expectedPackageVersion=request.expected_package_version,
        expectedPredecessorVersion=request.expected_predecessor_version,
        expectedOwnershipVersion=request.expected_ownership_version,
        authorisingGrantId=request.authorising_grant_id,
        expectedGrantVersion=request.expected_grant_version,
    )
    rebuilt = dependency_request(request.unit_id, request.package_id, payload)
    assert rebuilt == request
    actor_id, command_id = uuid4(), uuid4()
    command_payload = ChangeDependencyCommandPayload(
        commandId=command_id,
        idempotencyKey="dependency-contract",
        request=payload,
        previewHash="a" * 64,
    )
    command = dependency_command(request.unit_id, request.package_id, command_payload, actor_id)
    assert (command.command_id, command.actor_user_id, command.request) == (
        command_id,
        actor_id,
        request,
    )
    response = dependency_result(
        DependencyChangeResult(request.package_id, 2, request.predecessor_package_id, True, False)
    )
    assert response.package_version == 2


def test_remove_hash_differs_from_add_hash() -> None:
    request, actor = _request(), uuid4()
    assert dependency_change_hash(actor, request) != dependency_change_hash(
        actor, replace(request, operation=DependencyOperation.REMOVE)
    )
