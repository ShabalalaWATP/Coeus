"""Mapping and safe error contracts for organisation administration routes."""

from collections.abc import Callable

from coeus.core.errors import AppError
from coeus.domain.organisation import OrganisationUnit
from coeus.domain.organisation_bootstrap import (
    OrganisationBootstrapDenied,
    OrganisationBootstrapUnavailable,
)
from coeus.domain.organisation_lifecycle import (
    OrganisationMutationConflict,
    OrganisationMutationDenied,
    OrganisationMutationIdempotencyConflict,
    OrganisationMutationPreview,
    OrganisationMutationRequest,
    OrganisationMutationResult,
)
from coeus.schemas.organisation_admin import (
    OrganisationMutationPayload,
    OrganisationMutationPreviewResponse,
    OrganisationMutationResultResponse,
    OrganisationUnitResponse,
)


def mutation_request(payload: OrganisationMutationPayload) -> OrganisationMutationRequest:
    return OrganisationMutationRequest(
        payload.operation,
        payload.unit_id,
        payload.parent_unit_id,
        payload.expected_version,
        payload.name,
        payload.short_name,
        payload.category,
        payload.time_zone,
        payload.description,
        payload.authorising_grant_id,
        payload.reason,
    )


def unit_response(unit: OrganisationUnit) -> OrganisationUnitResponse:
    return OrganisationUnitResponse(**vars(unit))


def preview_response(
    preview: OrganisationMutationPreview,
) -> OrganisationMutationPreviewResponse:
    return OrganisationMutationPreviewResponse(**vars(preview))


def result_response(result: OrganisationMutationResult) -> OrganisationMutationResultResponse:
    return OrganisationMutationResultResponse(**vars(result))


def call_mutation[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except OrganisationMutationDenied as exc:
        raise AppError(
            403,
            "organisation_mutation_denied",
            "You do not have authority for this organisation change.",
        ) from exc
    except OrganisationMutationIdempotencyConflict as exc:
        raise AppError(409, "organisation_command_conflict", str(exc)) from exc
    except OrganisationMutationConflict as exc:
        raise AppError(409, "organisation_mutation_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "organisation_mutation_invalid", str(exc)) from exc


def call_bootstrap[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except OrganisationBootstrapDenied as exc:
        raise AppError(
            403,
            "organisation_bootstrap_denied",
            "Organisation bootstrap authorisation failed.",
        ) from exc
    except OrganisationBootstrapUnavailable as exc:
        raise AppError(
            409,
            "organisation_bootstrap_closed",
            "Organisation bootstrap is no longer available.",
        ) from exc
    except ValueError as exc:
        raise AppError(422, "organisation_bootstrap_invalid", str(exc)) from exc
