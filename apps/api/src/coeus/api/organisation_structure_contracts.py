"""Domain mappings for organisation structure administration."""

from collections.abc import Callable

from coeus.core.errors import AppError
from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationConflict,
    OrganisationDeactivationDenied,
    OrganisationDeactivationIdempotencyConflict,
    OrganisationDeactivationPreview,
    OrganisationDeactivationRequest,
)
from coeus.domain.organisation_reparent import (
    OrganisationReparentConflict,
    OrganisationReparentDenied,
    OrganisationReparentIdempotencyConflict,
    OrganisationReparentPreview,
    OrganisationReparentRequest,
)
from coeus.schemas.organisation_structure_admin import (
    DeactivationImpactResponse,
    DeactivationPreviewResponse,
    DeactivationRequestPayload,
    ReparentImpactResponse,
    ReparentPreviewResponse,
    ReparentRequestPayload,
)


def reparent_request(payload: ReparentRequestPayload) -> OrganisationReparentRequest:
    return OrganisationReparentRequest(
        payload.unit_id,
        payload.new_parent_unit_id,
        payload.expected_unit_version,
        payload.expected_parent_version,
        payload.authorising_grant_id,
        payload.reason,
    )


def deactivation_request(
    payload: DeactivationRequestPayload,
) -> OrganisationDeactivationRequest:
    return OrganisationDeactivationRequest(
        payload.unit_id,
        payload.expected_version,
        payload.authorising_grant_id,
        payload.reason,
    )


def reparent_preview_response(preview: OrganisationReparentPreview) -> ReparentPreviewResponse:
    return ReparentPreviewResponse(
        unit_id=preview.unit_id,
        new_parent_unit_id=preview.new_parent_unit_id,
        impact=ReparentImpactResponse(**vars(preview.impact)),
        preview_hash=preview.preview_hash,
    )


def deactivation_preview_response(
    preview: OrganisationDeactivationPreview,
) -> DeactivationPreviewResponse:
    return DeactivationPreviewResponse(
        request=DeactivationRequestPayload(**vars(preview.request)),
        impact=DeactivationImpactResponse(
            **vars(preview.impact), blocking_count=preview.impact.blocking_count
        ),
        preview_hash=preview.preview_hash,
    )


def call_structure[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except (OrganisationReparentDenied, OrganisationDeactivationDenied) as exc:
        raise AppError(
            403,
            "organisation_structure_denied",
            "You do not have authority for this organisation change.",
        ) from exc
    except (
        OrganisationReparentIdempotencyConflict,
        OrganisationDeactivationIdempotencyConflict,
    ) as exc:
        raise AppError(409, "organisation_command_conflict", str(exc)) from exc
    except (OrganisationReparentConflict, OrganisationDeactivationConflict) as exc:
        raise AppError(409, "organisation_structure_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "organisation_structure_invalid", str(exc)) from exc
