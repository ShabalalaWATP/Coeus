"""Domain mappings for single-home organisation workforce administration."""

from collections.abc import Callable

from coeus.core.errors import AppError
from coeus.domain.organisation_membership import (
    MembershipCommandConflict,
    MembershipCommandDenied,
    MembershipIdempotencyConflict,
    MembershipMutationPreview,
    MembershipMutationRequest,
)
from coeus.domain.organisation_transfer import (
    PersonnelTransferConflict,
    PersonnelTransferDenied,
    PersonnelTransferIdempotencyConflict,
    PersonnelTransferPreview,
    PersonnelTransferRequest,
)
from coeus.schemas.organisation_workforce_admin import (
    MembershipPreviewResponse,
    MembershipRequestPayload,
    MembershipSnapshotResponse,
    TransferImpactResponse,
    TransferPreviewResponse,
    TransferRequestPayload,
)


def membership_request(payload: MembershipRequestPayload) -> MembershipMutationRequest:
    return MembershipMutationRequest(
        payload.operation,
        payload.membership_id,
        payload.user_id,
        payload.unit_id,
        payload.expected_version,
        payload.role,
        payload.assignment_eligible,
        payload.valid_from,
        payload.valid_until,
        payload.authorising_grant_id,
        payload.reason,
    )


def transfer_request(payload: TransferRequestPayload) -> PersonnelTransferRequest:
    return PersonnelTransferRequest(
        payload.source_membership_id,
        payload.target_membership_id,
        payload.user_id,
        payload.source_unit_id,
        payload.target_unit_id,
        payload.expected_membership_version,
        payload.expected_target_unit_version,
        payload.target_role,
        payload.assignment_eligible,
        payload.effective_at,
        payload.source_authorising_grant_id,
        payload.target_authorising_grant_id,
        payload.reason,
    )


def membership_preview_response(
    preview: MembershipMutationPreview,
) -> MembershipPreviewResponse:
    return MembershipPreviewResponse(
        request=MembershipRequestPayload(**vars(preview.request)),
        snapshot=MembershipSnapshotResponse(**vars(preview.snapshot)),
        preview_hash=preview.preview_hash,
    )


def transfer_preview_response(preview: PersonnelTransferPreview) -> TransferPreviewResponse:
    return TransferPreviewResponse(
        request=TransferRequestPayload(**vars(preview.request)),
        impact=TransferImpactResponse(**vars(preview.impact)),
        preview_hash=preview.preview_hash,
    )


def call_workforce[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except (MembershipCommandDenied, PersonnelTransferDenied) as exc:
        raise AppError(
            403,
            "organisation_workforce_denied",
            "You do not have authority for this workforce change.",
        ) from exc
    except (
        MembershipIdempotencyConflict,
        PersonnelTransferIdempotencyConflict,
    ) as exc:
        raise AppError(409, "organisation_command_conflict", str(exc)) from exc
    except (MembershipCommandConflict, PersonnelTransferConflict) as exc:
        raise AppError(409, "organisation_workforce_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "organisation_workforce_invalid", str(exc)) from exc
