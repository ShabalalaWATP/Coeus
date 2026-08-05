"""Management-only reparent and deactivation routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from coeus.api.organisation_dependencies import (
    get_organisation_admin_csrf_session,
    get_organisation_administration,
)
from coeus.api.organisation_structure_contracts import (
    call_structure,
    deactivation_preview_response,
    deactivation_request,
    reparent_preview_response,
    reparent_request,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.organisation_deactivation import OrganisationDeactivationCommand
from coeus.domain.organisation_reparent import OrganisationReparentCommand
from coeus.organisation_administration_composition import OrganisationAdministration
from coeus.schemas.organisation_structure_admin import (
    DeactivationCommandPayload,
    DeactivationPreviewResponse,
    DeactivationRequestPayload,
    DeactivationResultResponse,
    ReparentCommandPayload,
    ReparentPreviewResponse,
    ReparentRequestPayload,
    ReparentResultResponse,
)

router = APIRouter(prefix="/admin/organisation", tags=["organisation administration"])
AdministrationDep = Annotated[OrganisationAdministration, Depends(get_organisation_administration)]
AdminSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_csrf_session)]


@router.post("/reparent-previews", response_model=ReparentPreviewResponse)
async def preview_reparent(
    payload: ReparentRequestPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> ReparentPreviewResponse:
    request = call_structure(lambda: reparent_request(payload))
    preview = call_structure(
        lambda: administration.reparent.preview(request, authenticated.user.user_id)
    )
    return reparent_preview_response(preview)


@router.post("/reparent-commands", response_model=ReparentResultResponse)
async def execute_reparent(
    payload: ReparentCommandPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> ReparentResultResponse:
    command = call_structure(
        lambda: OrganisationReparentCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            reparent_request(payload.request),
            payload.preview_hash,
        )
    )
    result = call_structure(lambda: administration.reparent.execute(command))
    return ReparentResultResponse(**vars(result))


@router.post("/deactivation-previews", response_model=DeactivationPreviewResponse)
async def preview_deactivation(
    payload: DeactivationRequestPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> DeactivationPreviewResponse:
    request = call_structure(lambda: deactivation_request(payload))
    preview = call_structure(
        lambda: administration.deactivation.preview(request, authenticated.user.user_id)
    )
    return deactivation_preview_response(preview)


@router.post("/deactivation-commands", response_model=DeactivationResultResponse)
async def execute_deactivation(
    payload: DeactivationCommandPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> DeactivationResultResponse:
    command = call_structure(
        lambda: OrganisationDeactivationCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            deactivation_request(payload.request),
            payload.preview_hash,
        )
    )
    result = call_structure(lambda: administration.deactivation.execute(command))
    return DeactivationResultResponse(**vars(result))
