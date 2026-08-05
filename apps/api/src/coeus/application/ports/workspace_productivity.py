"""Persistence boundary for workspace productivity records."""

from typing import Protocol
from uuid import UUID

from coeus.domain.workspace_productivity import (
    DeliveryPreferences,
    PackageTemplate,
    ProductivityCommand,
    RecordPage,
    SavedBoardView,
    WorkspaceStoreLink,
    WorkUpdate,
)


class WorkspaceProductivityStore(Protocol):
    def list_views(
        self, actor: UUID, cursor: UUID | None, limit: int
    ) -> RecordPage[SavedBoardView]: ...

    def save_view(self, command: ProductivityCommand) -> SavedBoardView: ...

    def delete_view(self, command: ProductivityCommand) -> bool: ...

    def list_templates(
        self, actor: UUID, unit_id: UUID, cursor: UUID | None, limit: int
    ) -> RecordPage[PackageTemplate]: ...

    def save_template(self, command: ProductivityCommand) -> PackageTemplate: ...

    def delete_template(self, command: ProductivityCommand) -> bool: ...

    def deliver_update(self, command: ProductivityCommand) -> WorkUpdate: ...

    def list_updates(
        self, actor: UUID, cursor: UUID | None, limit: int, unacknowledged_only: bool
    ) -> RecordPage[WorkUpdate]: ...

    def acknowledge_update(self, command: ProductivityCommand) -> WorkUpdate: ...

    def get_preferences(self, actor: UUID) -> DeliveryPreferences: ...

    def save_preferences(self, command: ProductivityCommand) -> DeliveryPreferences: ...

    def list_store_links(
        self,
        actor: UUID,
        unit_id: UUID,
        source_type: str,
        source_id: UUID,
        cursor: UUID | None,
        limit: int,
    ) -> RecordPage[WorkspaceStoreLink]: ...

    def save_store_link(self, command: ProductivityCommand) -> WorkspaceStoreLink: ...

    def delete_store_link(self, command: ProductivityCommand) -> bool: ...
