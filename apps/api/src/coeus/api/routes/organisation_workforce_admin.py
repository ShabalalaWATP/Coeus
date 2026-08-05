"""Management-only single-home membership and transfer routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.organisation_dependencies import (
    get_organisation_admin_csrf_session,
    get_organisation_admin_session,
    get_organisation_administration,
)
from coeus.api.organisation_workforce_contracts import (
    call_workforce,
    membership_preview_response,
    membership_request,
    transfer_preview_response,
    transfer_request,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.organisation_membership import MembershipMutationCommand
from coeus.domain.organisation_transfer import PersonnelTransferCommand
from coeus.organisation_administration_composition import OrganisationAdministration
from coeus.schemas.organisation_workforce_admin import (
    MembershipCommandPayload,
    MembershipListResponse,
    MembershipPreviewResponse,
    MembershipRecordResponse,
    MembershipRequestPayload,
    MembershipResultResponse,
    TransferCommandPayload,
    TransferPreviewResponse,
    TransferRequestPayload,
    TransferResultResponse,
)

router = APIRouter(prefix="/admin/organisation", tags=["organisation administration"])
AdministrationDep = Annotated[OrganisationAdministration, Depends(get_organisation_administration)]
AdminSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_csrf_session)]
AdminReadSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_session)]


@router.get(
    "/units/{unit_id}/memberships",
    response_model=MembershipListResponse,
)
async def list_unit_memberships(
    unit_id: UUID,
    authenticated: AdminReadSessionDep,
    administration: AdministrationDep,
    include_inactive: Annotated[bool, Query(alias="includeInactive")] = False,
) -> MembershipListResponse:
    del authenticated
    memberships = administration.repository.list_unit_memberships(
        unit_id, include_inactive=include_inactive
    )
    return MembershipListResponse(
        memberships=[MembershipRecordResponse(**vars(item)) for item in memberships]
    )


@router.get(
    "/users/{user_id}/memberships",
    response_model=MembershipListResponse,
)
async def list_user_memberships(
    user_id: UUID,
    authenticated: AdminReadSessionDep,
    administration: AdministrationDep,
) -> MembershipListResponse:
    del authenticated
    memberships = administration.repository.list_memberships(user_id)
    return MembershipListResponse(
        memberships=[MembershipRecordResponse(**vars(item)) for item in memberships]
    )


@router.post("/membership-previews", response_model=MembershipPreviewResponse)
async def preview_membership(
    payload: MembershipRequestPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> MembershipPreviewResponse:
    request = call_workforce(lambda: membership_request(payload))
    preview = call_workforce(
        lambda: administration.memberships.preview(request, authenticated.user.user_id)
    )
    return membership_preview_response(preview)


@router.post("/membership-commands", response_model=MembershipResultResponse)
async def execute_membership(
    payload: MembershipCommandPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> MembershipResultResponse:
    command = call_workforce(
        lambda: MembershipMutationCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            membership_request(payload.request),
            payload.preview_hash,
        )
    )
    result = call_workforce(lambda: administration.memberships.execute(command))
    return MembershipResultResponse(**vars(result))


@router.post("/transfer-previews", response_model=TransferPreviewResponse)
async def preview_transfer(
    payload: TransferRequestPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> TransferPreviewResponse:
    request = call_workforce(lambda: transfer_request(payload))
    preview = call_workforce(
        lambda: administration.transfers.preview(request, authenticated.user.user_id)
    )
    return transfer_preview_response(preview)


@router.post("/transfer-commands", response_model=TransferResultResponse)
async def execute_transfer(
    payload: TransferCommandPayload,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> TransferResultResponse:
    command = call_workforce(
        lambda: PersonnelTransferCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            transfer_request(payload.request),
            payload.preview_hash,
        )
    )
    result = call_workforce(lambda: administration.transfers.execute(command))
    return TransferResultResponse(**vars(result))
