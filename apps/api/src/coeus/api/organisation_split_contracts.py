"""Safe domain mappings for explicit organisation split administration."""

from collections.abc import Callable

from coeus.api.organisation_merge_contracts import disposition
from coeus.core.errors import AppError
from coeus.domain.organisation_merge import MergeUnitVersion
from coeus.domain.organisation_split import (
    OrganisationSplitConflict,
    OrganisationSplitDenied,
    OrganisationSplitIdempotencyConflict,
    OrganisationSplitImpact,
    OrganisationSplitPlan,
    OrganisationSplitRequest,
    SplitSuccessor,
)
from coeus.schemas.organisation_merge_admin import AffectedRecordResponse
from coeus.schemas.organisation_split_admin import (
    SplitImpactResponse,
    SplitPlanPayload,
    SplitRequestPayload,
)


def split_request(payload: SplitRequestPayload) -> OrganisationSplitRequest:
    return OrganisationSplitRequest(
        MergeUnitVersion(payload.source.unit_id, payload.source.expected_version),
        MergeUnitVersion(payload.parent.unit_id, payload.parent.expected_version),
        tuple(
            SplitSuccessor(
                item.unit_id,
                item.name,
                item.short_name,
                item.category,
                item.time_zone,
                item.description,
            )
            for item in payload.successors
        ),
        payload.source_authorising_grant_id,
        payload.parent_authorising_grant_id,
        payload.reason,
    )


def split_plan(payload: SplitPlanPayload) -> OrganisationSplitPlan:
    return OrganisationSplitPlan(
        split_request(payload.request),
        tuple(disposition(item) for item in payload.dispositions),
    )


def split_impact_response(impact: OrganisationSplitImpact) -> SplitImpactResponse:
    return SplitImpactResponse(
        records=[AffectedRecordResponse(**vars(item)) for item in impact.records],
        reservations=impact.reservations,
        team_calendar_events=impact.team_calendar_events,
        saved_views=impact.saved_views,
        state_digest=impact.state_digest,
    )


def call_split[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except OrganisationSplitDenied as exc:
        raise AppError(
            403,
            "organisation_split_denied",
            "You do not have authority for this organisation split.",
        ) from exc
    except OrganisationSplitIdempotencyConflict as exc:
        raise AppError(409, "organisation_command_conflict", str(exc)) from exc
    except OrganisationSplitConflict as exc:
        raise AppError(409, "organisation_split_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "organisation_split_invalid", str(exc)) from exc
