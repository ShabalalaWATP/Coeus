"""Safe HTTP mappings for dependency commands."""

from collections.abc import Callable
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangeRequest,
    DependencyChangeResult,
    WorkPackageDependencyConflict,
    WorkPackageDependencyDenied,
)
from coeus.schemas.work_package_dependencies import (
    ChangeDependencyCommandPayload,
    DependencyChangePayload,
    DependencyChangeResultResponse,
)


def dependency_request(
    unit_id: UUID, package_id: UUID, payload: DependencyChangePayload
) -> DependencyChangeRequest:
    return DependencyChangeRequest(
        unit_id,
        package_id,
        payload.predecessor_package_id,
        payload.operation,
        payload.expected_package_version,
        payload.expected_predecessor_version,
        payload.expected_ownership_version,
        payload.authorising_grant_id,
        payload.expected_grant_version,
    )


def dependency_command(
    unit_id: UUID,
    package_id: UUID,
    payload: ChangeDependencyCommandPayload,
    actor_user_id: UUID,
) -> ChangeDependencyCommand:
    return ChangeDependencyCommand(
        payload.command_id,
        payload.idempotency_key,
        actor_user_id,
        dependency_request(unit_id, package_id, payload.request),
        payload.preview_hash,
    )


def dependency_result(result: DependencyChangeResult) -> DependencyChangeResultResponse:
    return DependencyChangeResultResponse(**vars(result))


def call_dependency_change[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except WorkPackageDependencyDenied as exc:
        raise AppError(404, "work_package_not_found", "Work package was not found.") from exc
    except WorkPackageDependencyConflict as exc:
        raise AppError(409, "work_package_dependency_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "work_package_dependency_invalid", str(exc)) from exc
