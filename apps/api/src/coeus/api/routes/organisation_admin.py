"""Management-only organisation tree and unit lifecycle routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from coeus.api.dependencies import get_auth_service, get_settings
from coeus.api.organisation_contracts import (
    call_bootstrap,
    call_mutation,
    mutation_request,
    preview_response,
    result_response,
    unit_response,
)
from coeus.api.organisation_dependencies import (
    get_organisation_admin_csrf_session,
    get_organisation_admin_session,
    get_organisation_administration,
)
from coeus.api.routes.auth import client_ip
from coeus.api.synthetic_fixture_contracts import (
    call_fixture,
)
from coeus.api.synthetic_fixture_contracts import (
    preview_response as fixture_preview_response,
)
from coeus.api.synthetic_fixture_contracts import (
    result_response as fixture_result_response,
)
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.organisation_bootstrap import BootstrapOrganisationCommand
from coeus.domain.organisation_lifecycle import OrganisationMutationCommand
from coeus.domain.synthetic_organisation_fixture import SyntheticFixtureCommand
from coeus.organisation_administration_composition import OrganisationAdministration
from coeus.schemas.organisation_admin import (
    OrganisationBootstrapRequest,
    OrganisationBootstrapResponse,
    OrganisationMutationCommandRequest,
    OrganisationMutationPayload,
    OrganisationMutationPreviewResponse,
    OrganisationMutationResultResponse,
    OrganisationUnitListResponse,
    OrganisationUnitResponse,
)
from coeus.schemas.synthetic_organisation_fixture import (
    SyntheticFixtureCommandRequest,
    SyntheticFixturePreviewResponse,
    SyntheticFixtureResultResponse,
)
from coeus.services.auth import AuthService

router = APIRouter(prefix="/admin/organisation", tags=["organisation administration"])

AdministrationDep = Annotated[OrganisationAdministration, Depends(get_organisation_administration)]
AdminSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_session)]
AdminCsrfSessionDep = Annotated[AuthenticatedSession, Depends(get_organisation_admin_csrf_session)]


@router.post("/bootstrap", response_model=OrganisationBootstrapResponse)
async def bootstrap_organisation(
    payload: OrganisationBootstrapRequest,
    request: Request,
    authenticated: AdminCsrfSessionDep,
    administration: AdministrationDep,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OrganisationBootstrapResponse:
    auth_service.reauthenticate(
        authenticated,
        payload.current_password.get_secret_value(),
        client_ip=client_ip(request, settings),
    )
    command = call_bootstrap(
        lambda: BootstrapOrganisationCommand(
            payload.command_id,
            authenticated.user.user_id,
            payload.root_unit_id,
            payload.root_name,
            payload.root_short_name,
            payload.time_zone,
            payload.setup_nonce.get_secret_value(),
            payload.description,
        )
    )
    result = call_bootstrap(
        lambda: administration.bootstrap.execute(command, authenticated.user, reauthenticated=True)
    )
    return OrganisationBootstrapResponse(**vars(result))


@router.get("/units", response_model=OrganisationUnitListResponse)
async def list_units(
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
    parent_id: Annotated[UUID | None, Query(alias="parentId")] = None,
) -> OrganisationUnitListResponse:
    del authenticated
    units = (
        administration.repository.list_roots()
        if parent_id is None
        else administration.repository.list_children(parent_id)
    )
    return OrganisationUnitListResponse(units=[unit_response(item) for item in units])


@router.get("/units/{unit_id}", response_model=OrganisationUnitResponse)
async def get_unit(
    unit_id: UUID,
    authenticated: AdminSessionDep,
    administration: AdministrationDep,
) -> OrganisationUnitResponse:
    del authenticated
    unit = administration.repository.get_unit(unit_id)
    if unit is None:
        raise AppError(404, "organisation_unit_not_found", "Organisation unit was not found.")
    return unit_response(unit)


@router.post("/unit-previews", response_model=OrganisationMutationPreviewResponse)
async def preview_unit_mutation(
    payload: OrganisationMutationPayload,
    authenticated: AdminCsrfSessionDep,
    administration: AdministrationDep,
) -> OrganisationMutationPreviewResponse:
    request = call_mutation(lambda: mutation_request(payload))
    preview = call_mutation(
        lambda: administration.lifecycle.preview(request, authenticated.user.user_id)
    )
    return preview_response(preview)


@router.post("/unit-commands", response_model=OrganisationMutationResultResponse)
async def execute_unit_mutation(
    payload: OrganisationMutationCommandRequest,
    authenticated: AdminCsrfSessionDep,
    administration: AdministrationDep,
) -> OrganisationMutationResultResponse:
    command = call_mutation(
        lambda: OrganisationMutationCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            mutation_request(payload.request),
            payload.preview_hash,
        )
    )
    return result_response(call_mutation(lambda: administration.lifecycle.execute(command)))


@router.post(
    "/synthetic-fixture-preview",
    response_model=SyntheticFixturePreviewResponse,
)
async def preview_synthetic_fixture(
    authenticated: AdminCsrfSessionDep,
    administration: AdministrationDep,
) -> SyntheticFixturePreviewResponse:
    preview = call_fixture(lambda: administration.synthetic_fixture.preview(authenticated.user))
    return fixture_preview_response(preview)


@router.post(
    "/synthetic-fixture-commands",
    response_model=SyntheticFixtureResultResponse,
)
async def apply_synthetic_fixture(
    payload: SyntheticFixtureCommandRequest,
    request: Request,
    authenticated: AdminCsrfSessionDep,
    administration: AdministrationDep,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SyntheticFixtureResultResponse:
    auth_service.reauthenticate(
        authenticated,
        payload.current_password.get_secret_value(),
        client_ip=client_ip(request, settings),
    )
    command = call_fixture(
        lambda: SyntheticFixtureCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            payload.preview_hash,
        )
    )
    result = call_fixture(
        lambda: administration.synthetic_fixture.apply(
            command,
            authenticated.user,
            reauthenticated=True,
        )
    )
    return fixture_result_response(result)


@router.post(
    "/synthetic-fixture-reconcile-commands",
    response_model=SyntheticFixtureResultResponse,
)
async def reconcile_synthetic_fixture(
    payload: SyntheticFixtureCommandRequest,
    request: Request,
    authenticated: AdminCsrfSessionDep,
    administration: AdministrationDep,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SyntheticFixtureResultResponse:
    """Restore only reviewed, exact synthetic identifiers in local/test mode."""
    auth_service.reauthenticate(
        authenticated,
        payload.current_password.get_secret_value(),
        client_ip=client_ip(request, settings),
    )
    command = call_fixture(
        lambda: SyntheticFixtureCommand(
            payload.command_id,
            payload.idempotency_key,
            authenticated.user.user_id,
            payload.preview_hash,
        )
    )
    result = call_fixture(
        lambda: administration.synthetic_fixture.reconcile(
            command,
            authenticated.user,
            reauthenticated=True,
        )
    )
    return fixture_result_response(result)
