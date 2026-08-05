"""Application boundary for workspace productivity records."""

from dataclasses import replace
from uuid import UUID

from coeus.application.ports.workspace_productivity import WorkspaceProductivityStore
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.workspace_productivity import (
    DeliveryPreferences,
    PackageTemplate,
    ProductivityCommand,
    RecordPage,
    SavedBoardView,
    WorkspaceRecordDenied,
    WorkspaceStoreLink,
    WorkUpdate,
)
from coeus.services.store_access import StoreDetailService
from coeus.services.store_projects import StoreProjectService


class WorkspaceProductivityService:
    def __init__(
        self,
        store: WorkspaceProductivityStore,
        store_details: StoreDetailService | None = None,
        store_projects: StoreProjectService | None = None,
    ) -> None:
        self._store = store
        self._store_details = store_details
        self._store_projects = store_projects

    def list_views(
        self, actor: UUID, cursor: UUID | None, limit: int
    ) -> RecordPage[SavedBoardView]:
        return self._store.list_views(actor, cursor, limit)

    def save_view(self, command: ProductivityCommand) -> SavedBoardView:
        return self._store.save_view(command)

    def delete_view(self, command: ProductivityCommand) -> bool:
        return self._store.delete_view(command)

    def list_templates(
        self, actor: UUID, unit: UUID, cursor: UUID | None, limit: int
    ) -> RecordPage[PackageTemplate]:
        return self._store.list_templates(actor, unit, cursor, limit)

    def save_template(self, command: ProductivityCommand) -> PackageTemplate:
        return self._store.save_template(command)

    def delete_template(self, command: ProductivityCommand) -> bool:
        return self._store.delete_template(command)

    def deliver_update(self, command: ProductivityCommand) -> WorkUpdate:
        return self._store.deliver_update(command)

    def list_updates(
        self, actor: UUID, cursor: UUID | None, limit: int, pending: bool
    ) -> RecordPage[WorkUpdate]:
        return self._store.list_updates(actor, cursor, limit, pending)

    def acknowledge_update(self, command: ProductivityCommand) -> WorkUpdate:
        return self._store.acknowledge_update(command)

    def get_preferences(self, actor: UUID) -> DeliveryPreferences:
        return self._store.get_preferences(actor)

    def save_preferences(self, command: ProductivityCommand) -> DeliveryPreferences:
        return self._store.save_preferences(command)

    def list_store_links(
        self,
        actor: UserAccount,
        unit: UUID,
        source_type: str,
        source_id: UUID,
        cursor: UUID | None,
        limit: int,
    ) -> RecordPage[WorkspaceStoreLink]:
        visible: list[WorkspaceStoreLink] = []
        raw_cursor = cursor
        scanned = 0
        while len(visible) <= limit and scanned < 500:
            page = self._store.list_store_links(
                actor.user_id, unit, source_type, source_id, raw_cursor, 100
            )
            for item in page.items:
                scanned += 1
                resolved = self._resolve(actor, item)
                if resolved is not None:
                    visible.append(resolved)
                    if len(visible) > limit:
                        break
            if len(visible) > limit or page.next_cursor is None:
                break
            raw_cursor = page.next_cursor
        next_cursor = visible[limit - 1].link_id if len(visible) > limit else None
        return RecordPage(tuple(visible[:limit]), next_cursor)

    def save_store_link(
        self, actor: UserAccount, command: ProductivityCommand
    ) -> WorkspaceStoreLink:
        target_type = str(command.payload.get("target_type", ""))
        target_id = UUID(str(command.payload.get("target_id", "")))
        label = self._resolve_label(actor, target_type, target_id)
        enriched = ProductivityCommand(
            command.command_id,
            command.idempotency_key,
            command.actor_user_id,
            command.operation,
            {**command.payload, "label": label},
        )
        return self._store.save_store_link(enriched)

    def delete_store_link(self, command: ProductivityCommand) -> bool:
        return self._store.delete_store_link(command)

    def _resolve(self, actor: UserAccount, item: WorkspaceStoreLink) -> WorkspaceStoreLink | None:
        try:
            label = self._resolve_label(actor, item.target_type, item.target_id)
        except WorkspaceRecordDenied:
            return None
        return replace(item, label=label)

    def _resolve_label(self, actor: UserAccount, target_type: str, target_id: UUID) -> str:
        try:
            if target_type == "product" and self._store_details is not None:
                return self._store_details.get_visible_product(actor, target_id).metadata.title
            if target_type == "project" and self._store_projects is not None:
                return self._store_projects.get_for_member(actor.user_id, target_id).name
        except AppError as exc:
            raise WorkspaceRecordDenied from exc
        raise WorkspaceRecordDenied
