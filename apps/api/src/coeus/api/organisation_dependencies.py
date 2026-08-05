"""Dependencies for the separately gated organisation management plane."""

from typing import Annotated

from fastapi import Depends, Request

from coeus.api.dependencies import (
    get_auth_service,
    get_csrf_validated_session,
    get_current_session,
)
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession
from coeus.organisation_administration_composition import OrganisationAdministration
from coeus.services.auth import AuthService
from coeus.services.calendar_import import CalendarImportService
from coeus.services.cutover_activation import CutoverActivationService
from coeus.services.cutover_readiness import CutoverReadinessService
from coeus.services.my_work import MyWorkService
from coeus.services.organisation_workspace import OrganisationWorkspaceService
from coeus.services.package_predecessor_cancellation import PredecessorCancellationService
from coeus.services.team_capacity_forecast import TeamCapacityForecastService
from coeus.services.team_task_board import TeamTaskBoardService
from coeus.services.work_package_contributors import WorkPackageContributorService
from coeus.services.work_package_dependencies import WorkPackageDependencyService
from coeus.services.work_package_handovers import WorkPackageHandoverService
from coeus.services.work_package_planning import WorkPackagePlanningService
from coeus.services.workflow_leg_transfers import WorkflowLegTransferService
from coeus.services.workforce_calendar import WorkforceCalendarService
from coeus.services.workspace_operations import WorkspaceOperationsService
from coeus.services.workspace_productivity import WorkspaceProductivityService


def get_organisation_administration(request: Request) -> OrganisationAdministration:
    administration = getattr(request.app.state, "organisation_administration", None)
    if not isinstance(administration, OrganisationAdministration):
        raise AppError(
            503,
            "organisation_management_unavailable",
            "Organisation management is not enabled.",
        )
    return administration


def get_workforce_calendar(request: Request) -> WorkforceCalendarService:
    administration = get_organisation_administration(request)
    return administration.calendar


def get_organisation_workspace(request: Request) -> OrganisationWorkspaceService:
    administration = get_organisation_administration(request)
    return administration.workspace


def get_team_task_board(request: Request) -> TeamTaskBoardService:
    administration = get_organisation_administration(request)
    return administration.task_board


def get_work_package_planning(request: Request) -> WorkPackagePlanningService:
    administration = get_organisation_administration(request)
    return administration.work_package_planning


def get_work_package_contributors(request: Request) -> WorkPackageContributorService:
    administration = get_organisation_administration(request)
    return administration.work_package_contributors


def get_work_package_dependencies(request: Request) -> WorkPackageDependencyService:
    administration = get_organisation_administration(request)
    return administration.work_package_dependencies


def get_predecessor_cancellation(request: Request) -> PredecessorCancellationService:
    return get_organisation_administration(request).predecessor_cancellation


def get_work_package_handovers(request: Request) -> WorkPackageHandoverService:
    administration = get_organisation_administration(request)
    return administration.work_package_handovers


def get_workflow_leg_transfers(request: Request) -> WorkflowLegTransferService:
    return get_organisation_administration(request).workflow_leg_transfers


def get_my_work(request: Request) -> MyWorkService:
    administration = get_organisation_administration(request)
    return administration.my_work


def get_team_capacity_forecast(request: Request) -> TeamCapacityForecastService:
    administration = get_organisation_administration(request)
    return administration.team_capacity_forecast


def get_cutover_readiness(request: Request) -> CutoverReadinessService:
    administration = get_organisation_administration(request)
    return administration.cutover_readiness


def get_cutover_activation(request: Request) -> CutoverActivationService:
    service = getattr(request.app.state, "cutover_activation_service", None)
    if not isinstance(service, CutoverActivationService):
        raise AppError(503, "cutover_activation_unavailable", "Cutover activation is unavailable.")
    return service


def get_calendar_import(request: Request) -> CalendarImportService:
    administration = get_organisation_administration(request)
    return administration.calendar_import


def get_workspace_productivity(request: Request) -> WorkspaceProductivityService:
    administration = get_organisation_administration(request)
    return administration.workspace_productivity


def get_workspace_operations(request: Request) -> WorkspaceOperationsService:
    return get_organisation_administration(request).workspace_operations


def get_organisation_admin_session(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedSession:
    auth_service.require_permission(authenticated, Permission.SYSTEM_CONFIGURE)
    return authenticated


def get_organisation_admin_csrf_session(
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedSession:
    auth_service.require_permission(authenticated, Permission.SYSTEM_CONFIGURE)
    return authenticated
