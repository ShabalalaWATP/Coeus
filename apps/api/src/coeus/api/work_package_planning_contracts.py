"""Safe HTTP mappings for package planning."""

from collections.abc import Callable
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.work_package_planning import (
    PlanWorkPackageCommand,
    WorkPackagePlanningConflict,
    WorkPackagePlanningDenied,
    WorkPackagePlanningResult,
    WorkPackagePlanRequest,
)
from coeus.domain.work_packages import (
    CapacityAuthorityDenied,
    CapacityReservationConflict,
    CapacityUnavailable,
    CapacityUnknown,
)
from coeus.schemas.work_package_planning import (
    CapacityReservationResponse,
    PlanWorkPackageCommandPayload,
    WorkPackagePlanningResultResponse,
    WorkPackagePlanPayload,
)


def plan_request(
    unit_id: UUID, package_id: UUID, payload: WorkPackagePlanPayload
) -> WorkPackagePlanRequest:
    return WorkPackagePlanRequest(
        unit_id,
        package_id,
        payload.expected_package_version,
        payload.expected_ownership_version,
        payload.accountable_user_id,
        payload.estimated_minutes,
        payload.remaining_minutes,
        payload.due_at,
        payload.priority,
        payload.priority_override_reason,
        payload.reservation_id,
        payload.starts_at,
        payload.ends_at,
        payload.reserved_minutes,
        payload.authorising_grant_id,
    )


def plan_command(
    unit_id: UUID,
    package_id: UUID,
    payload: PlanWorkPackageCommandPayload,
    actor_user_id: UUID,
) -> PlanWorkPackageCommand:
    return PlanWorkPackageCommand(
        payload.command_id,
        payload.idempotency_key,
        actor_user_id,
        plan_request(unit_id, package_id, payload.request),
        payload.preview_hash,
    )


def planning_result(result: WorkPackagePlanningResult) -> WorkPackagePlanningResultResponse:
    reservation = result.reservation
    return WorkPackagePlanningResultResponse(
        package_id=result.package_id,
        package_version=result.package_version,
        reservation=CapacityReservationResponse(
            reservation_id=reservation.reservation_id,
            user_id=reservation.user_id,
            package_id=reservation.package_id,
            starts_at=reservation.starts_at,
            ends_at=reservation.ends_at,
            reserved_minutes=reservation.reserved_minutes,
            state=reservation.state.value,
            version=reservation.version,
        ),
        replayed=result.replayed,
    )


def call_planning[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except (WorkPackagePlanningDenied, CapacityAuthorityDenied) as exc:
        raise AppError(404, "work_package_not_found", "Work package was not found.") from exc
    except (
        WorkPackagePlanningConflict,
        CapacityReservationConflict,
        CapacityUnavailable,
    ) as exc:
        raise AppError(409, "work_package_planning_conflict", str(exc)) from exc
    except CapacityUnknown as exc:
        raise AppError(
            503,
            "work_package_capacity_unknown",
            "Current capacity evidence is incomplete. Refresh and try again.",
        ) from exc
    except ValueError as exc:
        raise AppError(422, "work_package_plan_invalid", str(exc)) from exc
