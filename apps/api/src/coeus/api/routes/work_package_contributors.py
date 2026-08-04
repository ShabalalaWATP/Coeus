"""Reviewed contributor lifecycle routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import get_csrf_validated_session
from coeus.api.organisation_dependencies import get_work_package_contributors
from coeus.api.work_package_contributor_contracts import (
    call_contributor_change,
    contributor_command,
    contributor_request,
    contributor_result,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.work_package_contributors import (
    ChangeContributorCommandPayload,
    ContributorChangePayload,
    ContributorChangePreviewResponse,
    ContributorChangeResultResponse,
)
from coeus.services.work_package_contributors import WorkPackageContributorService

router = APIRouter(
    prefix="/organisation/workspaces/{unit_id}/work-packages/{package_id}/contributors",
    tags=["work package contributors"],
)
SessionDep = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
ContributorDep = Annotated[WorkPackageContributorService, Depends(get_work_package_contributors)]


@router.post("/previews", response_model=ContributorChangePreviewResponse)
async def preview_contributor_change(
    unit_id: UUID,
    package_id: UUID,
    payload: ContributorChangePayload,
    authenticated: SessionDep,
    service: ContributorDep,
) -> ContributorChangePreviewResponse:
    preview = call_contributor_change(
        lambda: service.preview(
            authenticated.user.user_id,
            contributor_request(unit_id, package_id, payload),
        )
    )
    return ContributorChangePreviewResponse(**vars(preview))


@router.post("/commands", response_model=ContributorChangeResultResponse)
async def execute_contributor_change(
    unit_id: UUID,
    package_id: UUID,
    payload: ChangeContributorCommandPayload,
    authenticated: SessionDep,
    service: ContributorDep,
) -> ContributorChangeResultResponse:
    command = call_contributor_change(
        lambda: contributor_command(unit_id, package_id, payload, authenticated.user.user_id)
    )
    return contributor_result(call_contributor_change(lambda: service.execute(command)))
