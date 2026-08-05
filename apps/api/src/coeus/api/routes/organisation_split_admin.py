"""Management-only explicit-disposition organisation split routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from coeus.api.organisation_dependencies import (
    get_organisation_admin_csrf_session,
    get_organisation_administration,
)
from coeus.api.organisation_split_contracts import (
    call_split,
    split_impact_response,
    split_plan,
    split_request,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.organisation_split import OrganisationSplitCommand
from coeus.organisation_administration_composition import OrganisationAdministration
from coeus.schemas.organisation_merge_admin import UnitVersionPayload
from coeus.schemas.organisation_split_admin import (
    SplitCommandPayload,
    SplitImpactResponse,
    SplitPlanPayload,
    SplitPreviewResponse,
    SplitRequestPayload,
    SplitResultResponse,
)

router = APIRouter(prefix="/admin/organisation", tags=["organisation administration"])
AdministrationDep = Annotated[OrganisationAdministration, Depends(get_organisation_administration)]
AdminSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_csrf_session)]


@router.post("/split-assessments", response_model=SplitImpactResponse)
async def assess_split(
    payload: SplitRequestPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> SplitImpactResponse:
    request = call_split(lambda: split_request(payload))
    impact = call_split(lambda: administration.split.assess(request, authenticated.user.user_id))
    return split_impact_response(impact)


@router.post("/split-previews", response_model=SplitPreviewResponse)
async def preview_split(
    payload: SplitPlanPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> SplitPreviewResponse:
    preview = call_split(
        lambda: administration.split.preview(split_plan(payload), authenticated.user.user_id)
    )
    return SplitPreviewResponse(
        impact=split_impact_response(preview.impact), preview_hash=preview.preview_hash
    )


@router.post("/split-commands", response_model=SplitResultResponse)
async def execute_split(
    payload: SplitCommandPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> SplitResultResponse:
    command = call_split(
        lambda: OrganisationSplitCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            split_plan(payload.plan),
            payload.preview_hash,
        )
    )
    result = call_split(lambda: administration.split.execute(command))
    return SplitResultResponse(
        source=UnitVersionPayload(**vars(result.source)),
        parent=UnitVersionPayload(**vars(result.parent)),
        successors=[UnitVersionPayload(**vars(item)) for item in result.successors],
        replayed=result.replayed,
    )
