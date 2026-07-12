from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import (
    get_access_services,
    get_csrf_validated_session,
    get_current_session,
    require_permission,
)
from coeus.api.presenters.access import (
    to_acg_response,
    to_application_response,
    to_directory_user,
)
from coeus.core.permissions import Permission
from coeus.domain.access import AcgApplicationStatus
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.access import (
    AccessCheckResponse,
    AccessControlGroupListResponse,
    AccessControlGroupResponse,
    AccessDiagnosticsRequest,
    AccessDiagnosticsResponse,
    AcgAdminListResponse,
    AcgApplicationPageResponse,
    AcgApplicationResponse,
    AcgCatalogueItemResponse,
    AcgCatalogueResponse,
    ActiveUserDirectoryResponse,
    AddAccessControlGroupMemberRequest,
    CreateAccessControlGroupRequest,
    DecideAcgApplicationRequest,
    SubmitAcgApplicationRequest,
    UpdateAccessControlGroupRequest,
)
from coeus.services.access import AccessServices

router = APIRouter(tags=["access-control"])


@router.get("/acgs", response_model=AccessControlGroupListResponse)
async def list_acgs(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupListResponse:
    acgs = access_services.acgs.list_visible_acgs(authenticated.user)
    return AccessControlGroupListResponse(
        acgs=[to_acg_response(access_services, acg) for acg in acgs]
    )


@router.get("/acgs/catalogue", response_model=AcgCatalogueResponse)
async def list_acg_catalogue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=50)] = 20,
) -> AcgCatalogueResponse:
    acgs, total, total_pages = access_services.applications.catalogue(
        authenticated.user, page, page_size
    )
    return AcgCatalogueResponse(
        acgs=[
            AcgCatalogueItemResponse(
                acg_id=acg.acg_id,
                code=acg.code,
                name=acg.name,
                description=acg.description,
                is_member=access_services.applications.is_member(authenticated.user, acg.acg_id),
                application_status=(
                    application.status
                    if (
                        application := access_services.applications.own_application(
                            authenticated.user, acg.acg_id
                        )
                    )
                    else None
                ),
                application_id=(
                    application.application_id
                    if (
                        application := access_services.applications.own_application(
                            authenticated.user, acg.acg_id
                        )
                    )
                    else None
                ),
                can_review_applications=access_services.applications.can_review(
                    authenticated.user, acg.acg_id
                ),
                can_manage_admins=Permission.SYSTEM_CONFIGURE in authenticated.user.permissions,
            )
            for acg in acgs
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/acgs/admin-directory", response_model=ActiveUserDirectoryResponse)
async def list_acg_admin_directory(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
    query: Annotated[str, Query(max_length=100)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=50)] = 20,
) -> ActiveUserDirectoryResponse:
    users, total, total_pages = access_services.applications.active_user_directory(
        authenticated.user, query, page, page_size
    )
    return ActiveUserDirectoryResponse(
        users=[to_directory_user(user) for user in users],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.post("/acgs", response_model=AccessControlGroupResponse, status_code=201)
async def create_acg(
    payload: CreateAccessControlGroupRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupResponse:
    acg = access_services.acgs.create_acg(
        authenticated.user,
        payload.code,
        payload.name,
        payload.description,
        payload.owner_user_id,
    )
    return to_acg_response(access_services, acg)


@router.get("/acgs/{acg_id}", response_model=AccessControlGroupResponse)
async def get_acg(
    acg_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupResponse:
    acg = access_services.acgs.get_visible_acg(authenticated.user, acg_id)
    return to_acg_response(access_services, acg)


@router.patch("/acgs/{acg_id}", response_model=AccessControlGroupResponse)
async def update_acg(
    acg_id: UUID,
    payload: UpdateAccessControlGroupRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupResponse:
    acg = access_services.acgs.update_acg(
        authenticated.user,
        acg_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    return to_acg_response(access_services, acg)


@router.post("/acgs/{acg_id}/members", response_model=AccessControlGroupResponse)
async def add_acg_member(
    acg_id: UUID,
    payload: AddAccessControlGroupMemberRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupResponse:
    access_services.acgs.add_user(authenticated.user, acg_id, payload.user_id)
    acg = access_services.acgs.get_visible_acg(authenticated.user, acg_id)
    return to_acg_response(access_services, acg)


@router.delete("/acgs/{acg_id}/members/{user_id}", status_code=204)
async def remove_acg_member(
    acg_id: UUID,
    user_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> None:
    access_services.acgs.remove_user(authenticated.user, acg_id, user_id)


@router.post(
    "/acgs/{acg_id}/applications",
    response_model=AcgApplicationResponse,
    status_code=201,
)
async def submit_acg_application(
    acg_id: UUID,
    payload: SubmitAcgApplicationRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AcgApplicationResponse:
    application = access_services.applications.submit(
        authenticated.user, acg_id, payload.justification
    )
    return to_application_response(access_services, application)


@router.delete("/acgs/{acg_id}/applications/mine", status_code=204)
async def withdraw_acg_application(
    acg_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> None:
    access_services.applications.withdraw(authenticated.user, acg_id)


@router.get("/acg-applications", response_model=AcgApplicationPageResponse)
async def list_acg_applications(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=50)] = 20,
) -> AcgApplicationPageResponse:
    applications, total, total_pages = access_services.applications.review_queue(
        authenticated.user, page, page_size
    )
    return AcgApplicationPageResponse(
        applications=[
            to_application_response(access_services, application) for application in applications
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.post(
    "/acg-applications/{application_id}/decision",
    response_model=AcgApplicationResponse,
)
async def decide_acg_application(
    application_id: UUID,
    payload: DecideAcgApplicationRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AcgApplicationResponse:
    application = access_services.applications.decide(
        authenticated.user,
        application_id,
        (
            AcgApplicationStatus.APPROVED
            if payload.decision == "approve"
            else AcgApplicationStatus.REJECTED
        ),
        payload.reason,
    )
    return to_application_response(access_services, application)


@router.get("/acgs/{acg_id}/admins", response_model=AcgAdminListResponse)
async def list_acg_admins(
    acg_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AcgAdminListResponse:
    admins = access_services.applications.list_admins(authenticated.user, acg_id)
    return AcgAdminListResponse(admins=[to_directory_user(user) for user in admins])


@router.put("/acgs/{acg_id}/admins/{user_id}", response_model=AcgAdminListResponse)
async def add_acg_admin(
    acg_id: UUID,
    user_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AcgAdminListResponse:
    admins = access_services.applications.add_admin(authenticated.user, acg_id, user_id)
    return AcgAdminListResponse(admins=[to_directory_user(user) for user in admins])


@router.delete("/acgs/{acg_id}/admins/{user_id}", response_model=AcgAdminListResponse)
async def remove_acg_admin(
    acg_id: UUID,
    user_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AcgAdminListResponse:
    admins = access_services.applications.remove_admin(authenticated.user, acg_id, user_id)
    return AcgAdminListResponse(admins=[to_directory_user(user) for user in admins])


@router.post(
    "/store/products/{product_id}/access-diagnostics",
    response_model=AccessDiagnosticsResponse,
)
async def diagnose_product_access(
    product_id: UUID,
    payload: AccessDiagnosticsRequest,
    _authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    _csrf_validated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessDiagnosticsResponse:
    decision = access_services.diagnostics.diagnose_product(product_id, payload.user_id)
    return AccessDiagnosticsResponse(
        allowed=decision.allowed,
        reason=decision.reason,
        checks=[
            AccessCheckResponse(name=check.name, passed=check.passed, reason=check.reason)
            for check in decision.checks
        ],
    )
