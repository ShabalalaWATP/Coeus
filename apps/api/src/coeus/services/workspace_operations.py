"""Application policy for integrated team workspace operations."""

from dataclasses import replace
from uuid import UUID

from coeus.application.ports.workspace_operations import WorkspaceOperationsStore
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.store import StoreSearchFilters
from coeus.domain.workspace_operations import (
    CapabilityCoverage,
    WorkspaceAnalytics,
    WorkspaceCommand,
    WorkspaceExport,
    WorkspaceOverview,
    WorkspacePersonView,
    WorkspacePolicy,
    WorkspaceScope,
    WorkspaceSearchResult,
)
from coeus.repositories.access import AccessRepository
from coeus.services.store_access import StoreDetailService
from coeus.services.store_projects import StoreProjectService
from coeus.services.store_search import StoreSearchService


class WorkspaceOperationsService:
    def __init__(
        self,
        store: WorkspaceOperationsStore,
        users: AccessRepository,
        store_details: StoreDetailService,
        store_projects: StoreProjectService,
        store_search: StoreSearchService,
    ) -> None:
        self._store = store
        self._users = users
        self._store_details = store_details
        self._store_projects = store_projects
        self._store_search = store_search

    def overview(self, actor: UUID, unit: UUID, scope: WorkspaceScope) -> WorkspaceOverview:
        return self._store.overview(actor, unit, scope)

    def people(
        self, actor: UUID, unit: UUID, scope: WorkspaceScope, query: str | None, limit: int
    ) -> tuple[WorkspacePersonView, ...]:
        needle = (query or "").strip().casefold()
        visible: list[WorkspacePersonView] = []
        for item in self._store.people(actor, unit, scope):
            account = self._users.get_user(item.user_id)
            if account is None or not account.is_active:
                continue
            if (
                needle
                and needle not in account.display_name.casefold()
                and needle not in account.username.casefold()
            ):
                continue
            visible.append(
                WorkspacePersonView(
                    item.user_id,
                    account.display_name,
                    item.membership_role,
                    item.assignment_eligible,
                    _working_pattern(item.weekly_minutes, item.time_zone),
                )
            )
        return tuple(
            sorted(visible, key=lambda item: (item.display_name.casefold(), str(item.user_id)))[
                :limit
            ]
        )

    def capabilities(
        self, actor: UUID, unit: UUID, scope: WorkspaceScope
    ) -> tuple[CapabilityCoverage, ...]:
        return self._store.capabilities(actor, unit, scope)

    def policy(self, actor: UUID, unit: UUID) -> WorkspacePolicy:
        return self._store.policy(actor, unit)

    def save_policy(self, command: WorkspaceCommand) -> WorkspacePolicy:
        return self._store.save_policy(command)

    def search(
        self,
        actor: UserAccount,
        unit: UUID,
        scope: WorkspaceScope,
        query: str,
        limit: int,
        *,
        store_only: bool = False,
        offset: int = 0,
    ) -> tuple[WorkspaceSearchResult, ...]:
        candidates = (
            ()
            if store_only
            else self._store.search(
                actor.user_id, unit, scope, query, min((limit + offset) * 2, 100)
            )
        )
        resolved: list[WorkspaceSearchResult] = []
        for item in candidates:
            current = self._resolve_store_result(actor, item)
            if current is not None:
                if (
                    current.result_type == "person"
                    and query.casefold() not in current.label.casefold()
                ):
                    continue
                resolved.append(current)
            if len(resolved) == limit + offset:
                break
        if store_only:
            resolved.extend(self._search_store(actor, unit, query, limit + offset))
        return tuple(resolved[offset : offset + limit])

    def analytics(self, actor: UUID, unit: UUID, scope: WorkspaceScope) -> WorkspaceAnalytics:
        return self._store.analytics(actor, unit, scope)

    def create_export(self, command: WorkspaceCommand) -> WorkspaceExport:
        return self._store.create_export(command)

    def get_export(self, actor: UUID, export_id: UUID) -> WorkspaceExport:
        return self._store.get_export(actor, export_id)

    def export_csv(self, actor: UUID, export_id: UUID) -> bytes:
        return self._store.export_csv(actor, export_id)

    def _resolve_store_result(
        self, actor: UserAccount, item: WorkspaceSearchResult
    ) -> WorkspaceSearchResult | None:
        try:
            if item.result_type == "store_product":
                product = self._store_details.get_visible_product(actor, item.object_id)
                return replace(item, label=product.metadata.title)
            if item.result_type == "store_project":
                project = self._store_projects.get_for_member(actor.user_id, item.object_id)
                return replace(item, label=project.name)
            if item.result_type == "person":
                account = self._users.get_user(item.object_id)
                if account is None or not account.is_active:
                    return None
                return replace(item, label=account.display_name)
            return item
        except AppError:
            return None

    def _search_store(
        self, actor: UserAccount, unit: UUID, query: str, limit: int
    ) -> list[WorkspaceSearchResult]:
        results: list[WorkspaceSearchResult] = []
        try:
            products = self._store_search.search(
                actor, StoreSearchFilters(query=query, page=1, page_size=min(limit, 50))
            )
            results.extend(
                WorkspaceSearchResult(
                    "store_product",
                    hit.product.product_id,
                    unit,
                    hit.product.metadata.title,
                    f"Product · {hit.product.reference}",
                )
                for hit in products.hits
            )
        except AppError:
            pass
        needle = query.casefold()
        projects = sorted(
            self._store_projects.list_for_user(actor.user_id),
            key=lambda item: (item.name.casefold(), str(item.project_id)),
        )
        for project in projects:
            if project.archived or needle not in project.name.casefold():
                continue
            results.append(
                WorkspaceSearchResult(
                    "store_project", project.project_id, unit, project.name, "Store project"
                )
            )
        return results[:limit]


def _working_pattern(minutes: int | None, time_zone: str | None) -> str:
    if minutes is None or time_zone is None:
        return "Working pattern unavailable"
    hours, remainder = divmod(minutes, 60)
    duration = f"{hours}h" if remainder == 0 else f"{hours}h {remainder}m"
    return f"{duration} per week · {time_zone}"
