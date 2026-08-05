"""Safe domain mappings for explicit organisation merge administration."""

from collections.abc import Callable

from coeus.core.errors import AppError
from coeus.domain.organisation_merge import (
    MergeDisposition,
    MergeUnitAuthority,
    MergeUnitVersion,
    OrganisationMergeConflict,
    OrganisationMergeDenied,
    OrganisationMergeIdempotencyConflict,
    OrganisationMergeImpact,
    OrganisationMergePlan,
    OrganisationMergeRequest,
)
from coeus.schemas.organisation_merge_admin import (
    AffectedRecordResponse,
    DispositionPayload,
    MergeImpactResponse,
    MergePlanPayload,
    MergeRequestPayload,
)


def merge_request(payload: MergeRequestPayload) -> OrganisationMergeRequest:
    return OrganisationMergeRequest(
        tuple(MergeUnitVersion(item.unit_id, item.expected_version) for item in payload.sources),
        MergeUnitVersion(payload.successor.unit_id, payload.successor.expected_version),
        tuple(MergeUnitAuthority(item.unit_id, item.grant_id) for item in payload.authorities),
        payload.reason,
    )


def disposition(payload: DispositionPayload) -> MergeDisposition:
    return MergeDisposition(
        payload.kind,
        payload.record_id,
        payload.expected_version,
        payload.action,
        payload.target_unit_id,
        payload.replacement_id,
    )


def merge_plan(payload: MergePlanPayload) -> OrganisationMergePlan:
    return OrganisationMergePlan(
        merge_request(payload.request),
        tuple(disposition(item) for item in payload.dispositions),
    )


def merge_impact_response(impact: OrganisationMergeImpact) -> MergeImpactResponse:
    return MergeImpactResponse(
        records=[AffectedRecordResponse(**vars(item)) for item in impact.records],
        **{key: value for key, value in vars(impact).items() if key != "records"},
    )


def call_merge[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except OrganisationMergeDenied as exc:
        raise AppError(
            403,
            "organisation_merge_denied",
            "You do not have authority for this organisation merge.",
        ) from exc
    except OrganisationMergeIdempotencyConflict as exc:
        raise AppError(409, "organisation_command_conflict", str(exc)) from exc
    except OrganisationMergeConflict as exc:
        raise AppError(409, "organisation_merge_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "organisation_merge_invalid", str(exc)) from exc
