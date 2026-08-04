"""Safe HTTP mappings for contributor lifecycle changes."""

from collections.abc import Callable
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.work_package_contributors import (
    ChangeContributorCommand,
    ContributorCapacityPlan,
    ContributorChangeRequest,
    ContributorChangeResult,
    WorkPackageContributorConflict,
    WorkPackageContributorDenied,
)
from coeus.schemas.work_package_contributors import (
    ChangeContributorCommandPayload,
    ContributorChangePayload,
    ContributorChangeResultResponse,
)


def contributor_request(
    unit_id: UUID, package_id: UUID, payload: ContributorChangePayload
) -> ContributorChangeRequest:
    return ContributorChangeRequest(
        unit_id,
        package_id,
        payload.contributor_user_id,
        payload.operation,
        payload.expected_package_version,
        payload.expected_ownership_version,
        payload.authorising_grant_id,
        payload.expected_grant_version,
        payload.membership_id,
        payload.expected_membership_version,
        payload.expected_account_credential_version,
        payload.expected_account_source_hash,
        (
            ContributorCapacityPlan(
                payload.capacity_plan.reservation_id,
                payload.capacity_plan.starts_at,
                payload.capacity_plan.ends_at,
                payload.capacity_plan.reserved_minutes,
                payload.capacity_plan.idempotency_key,
            )
            if payload.capacity_plan is not None
            else None
        ),
    )


def contributor_command(
    unit_id: UUID,
    package_id: UUID,
    payload: ChangeContributorCommandPayload,
    actor_user_id: UUID,
) -> ChangeContributorCommand:
    return ChangeContributorCommand(
        payload.command_id,
        payload.idempotency_key,
        actor_user_id,
        contributor_request(unit_id, package_id, payload.request),
        payload.preview_hash,
    )


def contributor_result(result: ContributorChangeResult) -> ContributorChangeResultResponse:
    return ContributorChangeResultResponse(**vars(result))


def call_contributor_change[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except WorkPackageContributorDenied as exc:
        raise AppError(404, "work_package_not_found", "Work package was not found.") from exc
    except WorkPackageContributorConflict as exc:
        raise AppError(409, "work_package_contributor_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "work_package_contributor_invalid", str(exc)) from exc
