"""Management-only organisation grant routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.organisation_dependencies import (
    get_organisation_admin_csrf_session,
    get_organisation_admin_session,
    get_organisation_administration,
)
from coeus.api.organisation_grant_contracts import (
    call_grant,
    create_grant_command,
    grant_response,
    revoke_grant_command,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.organisation_administration_composition import OrganisationAdministration
from coeus.schemas.organisation_grant_admin import (
    CreateManagementGrantPayload,
    ManagementGrantListResponse,
    ManagementGrantResultResponse,
    RevokeManagementGrantPayload,
)

router = APIRouter(prefix="/admin/organisation", tags=["organisation administration"])
AdministrationDep = Annotated[OrganisationAdministration, Depends(get_organisation_administration)]
AdminSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_session)]
AdminCsrfSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_csrf_session)]


@router.get("/grants", response_model=ManagementGrantListResponse)
async def list_management_grants(
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
    root_unit_id: Annotated[UUID | None, Query(alias="rootUnitId")] = None,
    manager_user_id: Annotated[UUID | None, Query(alias="managerUserId")] = None,
    include_inactive: Annotated[bool, Query(alias="includeInactive")] = False,
) -> ManagementGrantListResponse:
    del authenticated
    grants = administration.repository.list_management_grants(
        root_unit_id=root_unit_id,
        manager_user_id=manager_user_id,
        include_inactive=include_inactive,
    )
    return ManagementGrantListResponse(grants=[grant_response(item) for item in grants])


@router.post("/grants", response_model=ManagementGrantResultResponse)
async def create_management_grant(
    payload: CreateManagementGrantPayload,
    authenticated: AdminCsrfSessionDep,
    administration: AdministrationDep,
) -> ManagementGrantResultResponse:
    command = call_grant(lambda: create_grant_command(payload, authenticated.user.user_id))
    return ManagementGrantResultResponse(
        **vars(call_grant(lambda: administration.grants.create(command)))
    )


@router.post("/grants/{grant_id}/revoke", response_model=ManagementGrantResultResponse)
async def revoke_management_grant(
    grant_id: UUID,
    payload: RevokeManagementGrantPayload,
    authenticated: AdminCsrfSessionDep,
    administration: AdministrationDep,
) -> ManagementGrantResultResponse:
    command = call_grant(
        lambda: revoke_grant_command(grant_id, payload, authenticated.user.user_id)
    )
    return ManagementGrantResultResponse(
        **vars(call_grant(lambda: administration.grants.revoke(command)))
    )
