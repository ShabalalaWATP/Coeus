"""Reviewed work-package dependency routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import get_csrf_validated_session
from coeus.api.organisation_dependencies import get_work_package_dependencies
from coeus.api.work_package_dependency_contracts import (
    call_dependency_change,
    dependency_command,
    dependency_request,
    dependency_result,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.work_package_dependencies import (
    ChangeDependencyCommandPayload,
    DependencyChangePayload,
    DependencyChangePreviewResponse,
    DependencyChangeResultResponse,
)
from coeus.services.work_package_dependencies import WorkPackageDependencyService

router = APIRouter(
    prefix="/organisation/workspaces/{unit_id}/work-packages/{package_id}/dependencies",
    tags=["work package dependencies"],
)
SessionDep = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
DependencyDep = Annotated[WorkPackageDependencyService, Depends(get_work_package_dependencies)]


@router.post("/previews", response_model=DependencyChangePreviewResponse)
async def preview_dependency_change(
    unit_id: UUID,
    package_id: UUID,
    payload: DependencyChangePayload,
    authenticated: SessionDep,
    service: DependencyDep,
) -> DependencyChangePreviewResponse:
    preview = call_dependency_change(
        lambda: service.preview(
            authenticated.user.user_id, dependency_request(unit_id, package_id, payload)
        )
    )
    return DependencyChangePreviewResponse(**vars(preview))


@router.post("/commands", response_model=DependencyChangeResultResponse)
async def execute_dependency_change(
    unit_id: UUID,
    package_id: UUID,
    payload: ChangeDependencyCommandPayload,
    authenticated: SessionDep,
    service: DependencyDep,
) -> DependencyChangeResultResponse:
    command = call_dependency_change(
        lambda: dependency_command(unit_id, package_id, payload, authenticated.user.user_id)
    )
    return dependency_result(call_dependency_change(lambda: service.execute(command)))
