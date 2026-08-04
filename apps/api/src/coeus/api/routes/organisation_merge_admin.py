"""Management-only explicit-disposition organisation merge routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from coeus.api.organisation_dependencies import (
    get_organisation_admin_csrf_session,
    get_organisation_administration,
)
from coeus.api.organisation_merge_contracts import (
    call_merge,
    merge_impact_response,
    merge_plan,
    merge_request,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.organisation_merge import OrganisationMergeCommand
from coeus.organisation_administration_composition import OrganisationAdministration
from coeus.schemas.organisation_merge_admin import (
    MergeCommandPayload,
    MergeImpactResponse,
    MergePlanPayload,
    MergePreviewResponse,
    MergeRequestPayload,
    MergeResultResponse,
    UnitVersionPayload,
)

router = APIRouter(prefix="/admin/organisation", tags=["organisation administration"])
AdministrationDep = Annotated[OrganisationAdministration, Depends(get_organisation_administration)]
AdminSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_csrf_session)]


@router.post("/merge-assessments", response_model=MergeImpactResponse)
async def assess_merge(
    payload: MergeRequestPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> MergeImpactResponse:
    request = call_merge(lambda: merge_request(payload))
    impact = call_merge(lambda: administration.merge.assess(request, authenticated.user.user_id))
    return merge_impact_response(impact)


@router.post("/merge-previews", response_model=MergePreviewResponse)
async def preview_merge(
    payload: MergePlanPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> MergePreviewResponse:
    preview = call_merge(
        lambda: administration.merge.preview(merge_plan(payload), authenticated.user.user_id)
    )
    return MergePreviewResponse(
        impact=merge_impact_response(preview.impact), preview_hash=preview.preview_hash
    )


@router.post("/merge-commands", response_model=MergeResultResponse)
async def execute_merge(
    payload: MergeCommandPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> MergeResultResponse:
    command = call_merge(
        lambda: OrganisationMergeCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            merge_plan(payload.plan),
            payload.preview_hash,
        )
    )
    result = call_merge(lambda: administration.merge.execute(command))
    return MergeResultResponse(
        successor_unit_id=result.successor_unit_id,
        successor_version=result.successor_version,
        source_versions=[UnitVersionPayload(**vars(item)) for item in result.source_versions],
        replayed=result.replayed,
    )
