"""Previewed manager package-planning route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import get_csrf_validated_session
from coeus.api.organisation_dependencies import get_work_package_planning
from coeus.api.work_package_planning_contracts import (
    call_planning,
    plan_command,
    plan_request,
    planning_result,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.work_package_planning import (
    PlanWorkPackageCommandPayload,
    WorkPackagePlanningPreviewResponse,
    WorkPackagePlanningResultResponse,
    WorkPackagePlanPayload,
)
from coeus.services.work_package_planning import WorkPackagePlanningService

router = APIRouter(
    prefix="/organisation/workspaces/{unit_id}/work-packages/{package_id}/planning",
    tags=["work package planning"],
)
SessionDep = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
PlanningDep = Annotated[WorkPackagePlanningService, Depends(get_work_package_planning)]


@router.post("/previews", response_model=WorkPackagePlanningPreviewResponse)
async def preview_plan(
    unit_id: UUID,
    package_id: UUID,
    payload: WorkPackagePlanPayload,
    authenticated: SessionDep,
    service: PlanningDep,
) -> WorkPackagePlanningPreviewResponse:
    preview = call_planning(
        lambda: service.preview(
            authenticated.user.user_id, plan_request(unit_id, package_id, payload)
        )
    )
    return WorkPackagePlanningPreviewResponse(**vars(preview))


@router.post("/commands", response_model=WorkPackagePlanningResultResponse)
async def execute_plan(
    unit_id: UUID,
    package_id: UUID,
    payload: PlanWorkPackageCommandPayload,
    authenticated: SessionDep,
    service: PlanningDep,
) -> WorkPackagePlanningResultResponse:
    command = call_planning(
        lambda: plan_command(unit_id, package_id, payload, authenticated.user.user_id)
    )
    return planning_result(call_planning(lambda: service.execute(command)))
