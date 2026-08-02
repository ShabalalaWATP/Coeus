from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_store_services,
)
from coeus.api.presenters.store_organisation import (
    project_detail,
    project_summary,
    subscription_response,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.store_organisation import (
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectEntryCreateRequest,
    ProjectMemberAddRequest,
    ProjectStatusRequest,
    ProjectSummaryResponse,
    SubscriptionResponse,
    SubscriptionUpsertRequest,
)
from coeus.services.store import StoreServices
from coeus.services.store_subscriptions import SubscriptionCriteria

router = APIRouter()
CurrentSession = Annotated[AuthenticatedSession, Depends(get_current_session)]
MutationSession = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
StoreDep = Annotated[StoreServices, Depends(get_store_services)]


@router.get("/projects", response_model=list[ProjectSummaryResponse])
async def list_projects(
    authenticated: CurrentSession, store: StoreDep
) -> list[ProjectSummaryResponse]:
    return [
        project_summary(project, authenticated.user, store)
        for project in store.projects.list_for_user(authenticated.user.user_id)
    ]


@router.post("/projects", response_model=ProjectDetailResponse, status_code=201)
async def create_project(
    payload: ProjectCreateRequest,
    authenticated: MutationSession,
    store: StoreDep,
) -> ProjectDetailResponse:
    project = store.projects.create(
        authenticated.user,
        name=payload.name,
        purpose=payload.purpose,
        region=payload.region,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )
    return project_detail(project, authenticated.user, store)


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID, authenticated: CurrentSession, store: StoreDep
) -> ProjectDetailResponse:
    project = store.projects.get_for_member(authenticated.user.user_id, project_id)
    return project_detail(project, authenticated.user, store)


@router.post("/projects/{project_id}/members", response_model=ProjectDetailResponse)
async def add_project_member(
    project_id: UUID,
    payload: ProjectMemberAddRequest,
    authenticated: MutationSession,
    store: StoreDep,
) -> ProjectDetailResponse:
    project = store.projects.add_member(authenticated.user, project_id, payload.username)
    return project_detail(project, authenticated.user, store)


@router.delete(
    "/projects/{project_id}/members/{member_user_id}",
    response_model=ProjectDetailResponse,
)
async def remove_project_member(
    project_id: UUID,
    member_user_id: UUID,
    authenticated: MutationSession,
    store: StoreDep,
) -> ProjectDetailResponse:
    project = store.projects.remove_member(authenticated.user, project_id, member_user_id)
    return project_detail(project, authenticated.user, store)


@router.put("/projects/{project_id}/status", response_model=ProjectDetailResponse)
async def update_project_status(
    project_id: UUID,
    payload: ProjectStatusRequest,
    authenticated: MutationSession,
    store: StoreDep,
) -> ProjectDetailResponse:
    project = store.projects.set_archived(authenticated.user, project_id, payload.archived)
    return project_detail(project, authenticated.user, store)


@router.put("/projects/{project_id}/products/{product_id}", response_model=ProjectDetailResponse)
async def add_project_product(
    project_id: UUID,
    product_id: UUID,
    authenticated: MutationSession,
    store: StoreDep,
) -> ProjectDetailResponse:
    store.details.get_visible_product(authenticated.user, product_id)
    project = store.projects.add_product(authenticated.user, project_id, product_id)
    return project_detail(project, authenticated.user, store)


@router.delete("/projects/{project_id}/products/{product_id}", response_model=ProjectDetailResponse)
async def remove_project_product(
    project_id: UUID,
    product_id: UUID,
    authenticated: MutationSession,
    store: StoreDep,
) -> ProjectDetailResponse:
    store.details.get_visible_product(authenticated.user, product_id)
    project = store.projects.remove_product(authenticated.user, project_id, product_id)
    return project_detail(project, authenticated.user, store)


@router.post("/projects/{project_id}/entries", response_model=ProjectDetailResponse)
async def add_project_entry(
    project_id: UUID,
    payload: ProjectEntryCreateRequest,
    authenticated: MutationSession,
    store: StoreDep,
) -> ProjectDetailResponse:
    project = store.projects.add_entry(authenticated.user, project_id, payload.kind, payload.body)
    return project_detail(project, authenticated.user, store)


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    authenticated: CurrentSession, store: StoreDep
) -> list[SubscriptionResponse]:
    return [
        subscription_response(item)
        for item in store.subscriptions.list_for_user(authenticated.user.user_id)
    ]


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    payload: SubscriptionUpsertRequest,
    authenticated: MutationSession,
    store: StoreDep,
) -> SubscriptionResponse:
    subscription = store.subscriptions.create(
        authenticated.user.user_id,
        name=payload.name,
        cadence=payload.cadence,
        criteria=_criteria(payload),
    )
    return subscription_response(subscription)


@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    payload: SubscriptionUpsertRequest,
    authenticated: MutationSession,
    store: StoreDep,
) -> SubscriptionResponse:
    subscription = store.subscriptions.update(
        authenticated.user.user_id,
        subscription_id,
        name=payload.name,
        cadence=payload.cadence,
        enabled=payload.enabled,
        criteria=_criteria(payload),
    )
    return subscription_response(subscription)


@router.delete("/subscriptions/{subscription_id}", status_code=204)
async def delete_subscription(
    subscription_id: UUID,
    authenticated: MutationSession,
    store: StoreDep,
) -> Response:
    store.subscriptions.delete(authenticated.user.user_id, subscription_id)
    return Response(status_code=204)


def _criteria(payload: SubscriptionUpsertRequest) -> SubscriptionCriteria:
    criteria = payload.criteria
    return SubscriptionCriteria(
        query=criteria.query,
        product_type=criteria.product_type,
        region=criteria.region,
        tag=criteria.tag,
        source_type=criteria.source_type,
        date_from=criteria.date_from,
        date_to=criteria.date_to,
    )
