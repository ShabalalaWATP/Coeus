"""Safe mappings for predecessor cancellation commands."""

from collections.abc import Callable
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    DependantDisposition,
    PredecessorCancellationConflict,
    PredecessorCancellationDenied,
    PredecessorCancellationRequest,
    PredecessorCancellationResult,
)
from coeus.schemas.package_predecessor_cancellation import (
    CancelPredecessorCommandPayload,
    PredecessorCancellationPayload,
    PredecessorCancellationResultResponse,
)


def cancellation_request(
    unit_id: UUID, package_id: UUID, payload: PredecessorCancellationPayload
) -> PredecessorCancellationRequest:
    return PredecessorCancellationRequest(
        unit_id,
        package_id,
        payload.expected_package_version,
        payload.expected_ownership_version,
        payload.authorising_grant_id,
        payload.expected_grant_version,
        tuple(
            DependantDisposition(
                item.dependant_package_id,
                item.expected_version,
                item.action,
                item.replacement_package_id,
                item.expected_replacement_version,
            )
            for item in payload.dispositions
        ),
    )


def cancellation_command(
    unit_id: UUID,
    package_id: UUID,
    payload: CancelPredecessorCommandPayload,
    actor_user_id: UUID,
) -> CancelPredecessorCommand:
    return CancelPredecessorCommand(
        payload.command_id,
        payload.idempotency_key,
        actor_user_id,
        cancellation_request(unit_id, package_id, payload.request),
        payload.preview_hash,
    )


def cancellation_result(
    result: PredecessorCancellationResult,
) -> PredecessorCancellationResultResponse:
    return PredecessorCancellationResultResponse(**vars(result))


def call_cancellation[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except PredecessorCancellationDenied as exc:
        raise AppError(404, "work_package_not_found", "Work package was not found.") from exc
    except PredecessorCancellationConflict as exc:
        raise AppError(409, "predecessor_cancellation_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "predecessor_cancellation_invalid", str(exc)) from exc
