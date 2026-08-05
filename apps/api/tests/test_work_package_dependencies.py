"""Focused contracts for reviewed dependency commands."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.api.work_package_dependency_contracts import call_dependency_change
from coeus.core.errors import AppError
from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangePreview,
    DependencyChangeRequest,
    DependencyChangeResult,
    DependencyOperation,
    WorkPackageDependencyConflict,
    WorkPackageDependencyDenied,
    dependency_change_hash,
    validate_bounded_dependency_graph,
)
from coeus.services.work_package_dependencies import WorkPackageDependencyService


def _request(**changes: object) -> DependencyChangeRequest:
    values: dict[str, object] = {
        "unit_id": uuid4(),
        "package_id": uuid4(),
        "predecessor_package_id": uuid4(),
        "operation": DependencyOperation.ADD,
        "expected_package_version": 2,
        "expected_predecessor_version": 3,
        "expected_ownership_version": 4,
        "authorising_grant_id": uuid4(),
        "expected_grant_version": 5,
    }
    values.update(changes)
    return DependencyChangeRequest(**values)  # type: ignore[arg-type]


def test_request_and_command_validation_and_exact_hash() -> None:
    request = _request()
    actor_id = uuid4()
    digest = dependency_change_hash(actor_id, request)
    assert digest == dependency_change_hash(actor_id, request)
    assert digest != dependency_change_hash(actor_id, replace(request, expected_grant_version=6))
    with pytest.raises(ValueError, match="versions"):
        _request(expected_package_version=0)
    with pytest.raises(ValueError, match="itself"):
        _request(package_id=request.package_id, predecessor_package_id=request.package_id)
    with pytest.raises(ValueError, match="idempotency"):
        ChangeDependencyCommand(uuid4(), "", actor_id, request, digest)
    with pytest.raises(ValueError, match="preview"):
        ChangeDependencyCommand(uuid4(), "dependency", actor_id, request, "x" * 64)


def test_bounded_graph_oracle_accepts_dag_and_rejects_unsafe_graphs() -> None:
    first, second, third = uuid4(), uuid4(), uuid4()
    validate_bounded_dependency_graph((first, second, third), ((second, first), (third, second)))
    with pytest.raises(WorkPackageDependencyConflict, match="acyclic"):
        validate_bounded_dependency_graph((first, second), ((first, second), (second, first)))
    with pytest.raises(WorkPackageDependencyConflict, match="duplicate"):
        validate_bounded_dependency_graph((first, first), ())
    with pytest.raises(WorkPackageDependencyDenied, match="incomplete"):
        validate_bounded_dependency_graph((first,), ((first, second),))
    with pytest.raises(WorkPackageDependencyConflict, match="itself"):
        validate_bounded_dependency_graph((first,), ((first, first),))
    with pytest.raises(WorkPackageDependencyDenied, match="boundary"):
        validate_bounded_dependency_graph(tuple(uuid4() for _ in range(129)), ())
    with pytest.raises(WorkPackageDependencyDenied, match="boundary"):
        validate_bounded_dependency_graph(
            (first, second), tuple((first, second) for _ in range(513))
        )


class _Store:
    def __init__(self, request: DependencyChangeRequest) -> None:
        self.request = request

    def preview(
        self, actor_user_id: UUID, request: DependencyChangeRequest
    ) -> DependencyChangePreview:
        return DependencyChangePreview(
            dependency_change_hash(actor_user_id, request),
            request.package_id,
            2,
            request.predecessor_package_id,
            3,
            4,
            False,
            3,
        )

    def execute(self, command: ChangeDependencyCommand) -> DependencyChangeResult:
        return DependencyChangeResult(
            command.request.package_id,
            3,
            command.request.predecessor_package_id,
            True,
            False,
        )


def test_service_delegates_preview_and_execution() -> None:
    request, actor_id = _request(), uuid4()
    service = WorkPackageDependencyService(_Store(request))
    preview = service.preview(actor_id, request)
    result = service.execute(
        ChangeDependencyCommand(uuid4(), "dependency", actor_id, request, preview.preview_hash)
    )
    assert preview.planned_package_version == 3
    assert result.dependency_active


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (WorkPackageDependencyDenied("hidden"), 404, "work_package_not_found"),
        (WorkPackageDependencyConflict("stale"), 409, "work_package_dependency_conflict"),
        (ValueError("invalid"), 422, "work_package_dependency_invalid"),
    ],
)
def test_http_error_mapping(error: Exception, status: int, code: str) -> None:
    with pytest.raises(AppError) as raised:
        call_dependency_change(lambda: (_ for _ in ()).throw(error))
    assert (raised.value.status_code, raised.value.code) == (status, code)


def test_service_protocol_fixture_is_structurally_complete() -> None:
    request = _request()
    assert SimpleNamespace(request=request).request.operation is DependencyOperation.ADD
