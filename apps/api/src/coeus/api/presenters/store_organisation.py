from uuid import UUID

from coeus.api.presenters.store import product_response
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.store_projects import StoreProject
from coeus.schemas.store import StoreProductResponse
from coeus.schemas.store_organisation import (
    ProjectActivityResponse,
    ProjectDetailResponse,
    ProjectEntryResponse,
    ProjectMemberResponse,
    ProjectSummaryResponse,
    SubscriptionCriteriaResponse,
    SubscriptionResponse,
)
from coeus.services.store import StoreServices
from coeus.services.store_subscriptions import StoreSubscription


def project_summary(
    project: StoreProject, actor: UserAccount, store: StoreServices
) -> ProjectSummaryResponse:
    visible, _visible_ids = _visible_products(project, actor, store)
    return ProjectSummaryResponse(
        project_id=project.project_id,
        name=project.name,
        purpose=project.purpose,
        region=project.region,
        date_from=project.date_from,
        date_to=project.date_to,
        archived=project.archived,
        owner=project.owner_user_id == actor.user_id,
        member_count=len(project.member_user_ids),
        visible_product_count=len(visible),
        updated_at=project.updated_at,
    )


def project_detail(
    project: StoreProject, actor: UserAccount, store: StoreServices
) -> ProjectDetailResponse:
    products, visible_ids = _visible_products(project, actor, store)
    members = {
        member_id: _member(project, member_id, store) for member_id in project.member_user_ids
    }
    entries = [
        ProjectEntryResponse(
            entry_id=entry.entry_id,
            kind=entry.kind,
            body=entry.body,
            author=members.get(entry.author_user_id)
            or _former_member(entry.author_user_id, project),
            created_at=entry.created_at,
        )
        for entry in project.entries
    ]
    activity = [
        ProjectActivityResponse(
            activity_id=item.activity_id,
            action=item.action,
            actor_display_name=_display_name(item.actor_user_id, store),
            occurred_at=item.occurred_at,
        )
        for item in project.activity
        if item.product_id is None or item.product_id in visible_ids
    ]
    summary = project_summary(project, actor, store)
    return ProjectDetailResponse(
        **summary.model_dump(),
        members=list(members.values()),
        products=products,
        entries=entries,
        activity=activity,
    )


def subscription_response(subscription: StoreSubscription) -> SubscriptionResponse:
    criteria = subscription.criteria
    return SubscriptionResponse(
        subscription_id=subscription.subscription_id,
        name=subscription.name,
        cadence=subscription.cadence,
        enabled=subscription.enabled,
        criteria=SubscriptionCriteriaResponse(
            query=criteria.query,
            product_type=criteria.product_type,
            region=criteria.region,
            tag=criteria.tag,
            source_type=criteria.source_type,
            date_from=criteria.date_from,
            date_to=criteria.date_to,
        ),
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )


def _visible_products(
    project: StoreProject, actor: UserAccount, store: StoreServices
) -> tuple[list[StoreProductResponse], set[UUID]]:
    products: list[StoreProductResponse] = []
    visible_ids: set[UUID] = set()
    for product_id in project.product_ids:
        try:
            product = store.details.get_visible_product(actor, product_id)
        except AppError as exc:
            if exc.status_code != 404:
                raise
            continue
        products.append(product_response(product))
        visible_ids.add(product_id)
    return products, visible_ids


def _member(project: StoreProject, user_id: UUID, store: StoreServices) -> ProjectMemberResponse:
    user = store.projects.user_account(user_id)
    if user is None:
        return _former_member(user_id, project)
    return ProjectMemberResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        owner=user.user_id == project.owner_user_id,
    )


def _former_member(user_id: UUID, project: StoreProject) -> ProjectMemberResponse:
    return ProjectMemberResponse(
        user_id=user_id,
        username="",
        display_name="Former member",
        owner=user_id == project.owner_user_id,
    )


def _display_name(user_id: UUID, store: StoreServices) -> str:
    user = store.projects.user_account(user_id)
    return user.display_name if user else "Former member"
