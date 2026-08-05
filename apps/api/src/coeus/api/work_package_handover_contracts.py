"""Safe HTTP mappings for accountable-owner handover."""

from collections.abc import Callable
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    ReservationHandover,
    WorkPackageHandoverConflict,
    WorkPackageHandoverDenied,
    WorkPackageHandoverRequest,
    WorkPackageHandoverResult,
)
from coeus.schemas.work_package_handovers import (
    HandoverWorkPackageCommandPayload,
    WorkPackageHandoverPayload,
    WorkPackageHandoverResultResponse,
)


def handover_request(
    unit_id: UUID, package_id: UUID, payload: WorkPackageHandoverPayload
) -> WorkPackageHandoverRequest:
    return WorkPackageHandoverRequest(
        unit_id,
        package_id,
        payload.target_user_id,
        payload.expected_package_version,
        payload.expected_ownership_version,
        payload.authorising_grant_id,
        payload.expected_grant_version,
        payload.target_membership_id,
        payload.expected_target_membership_version,
        payload.expected_target_account_credential_version,
        payload.expected_target_account_source_hash,
        payload.expected_ticket_version,
        payload.expected_ticket_source_hash,
        tuple(
            ReservationHandover(
                item.source_reservation_id,
                item.expected_source_version,
                item.disposition,
                item.replacement_reservation_id,
                item.replacement_idempotency_key,
            )
            for item in payload.reservations
        ),
    )


def handover_command(
    unit_id: UUID,
    package_id: UUID,
    payload: HandoverWorkPackageCommandPayload,
    actor_user_id: UUID,
) -> HandoverWorkPackageCommand:
    return HandoverWorkPackageCommand(
        payload.command_id,
        payload.idempotency_key,
        actor_user_id,
        handover_request(unit_id, package_id, payload.request),
        payload.preview_hash,
    )


def handover_result(result: WorkPackageHandoverResult) -> WorkPackageHandoverResultResponse:
    return WorkPackageHandoverResultResponse(**vars(result))


def call_handover[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except WorkPackageHandoverDenied as exc:
        raise AppError(404, "work_package_not_found", "Work package was not found.") from exc
    except WorkPackageHandoverConflict as exc:
        raise AppError(409, "work_package_handover_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "work_package_handover_invalid", str(exc)) from exc
