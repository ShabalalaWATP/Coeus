"""Persistence boundary for integrated workspace operations."""

from typing import Protocol
from uuid import UUID

from coeus.domain.workspace_operations import (
    CapabilityCoverage,
    WorkspaceAnalytics,
    WorkspaceCommand,
    WorkspaceExport,
    WorkspaceOverview,
    WorkspacePerson,
    WorkspacePolicy,
    WorkspaceScope,
    WorkspaceSearchResult,
)


class WorkspaceOperationsStore(Protocol):
    def overview(self, actor: UUID, unit_id: UUID, scope: WorkspaceScope) -> WorkspaceOverview: ...

    def people(
        self, actor: UUID, unit_id: UUID, scope: WorkspaceScope
    ) -> tuple[WorkspacePerson, ...]: ...

    def capabilities(
        self, actor: UUID, unit_id: UUID, scope: WorkspaceScope
    ) -> tuple[CapabilityCoverage, ...]: ...

    def policy(self, actor: UUID, unit_id: UUID) -> WorkspacePolicy: ...

    def save_policy(self, command: WorkspaceCommand) -> WorkspacePolicy: ...

    def search(
        self, actor: UUID, unit_id: UUID, scope: WorkspaceScope, query: str, limit: int
    ) -> tuple[WorkspaceSearchResult, ...]: ...

    def analytics(
        self, actor: UUID, unit_id: UUID, scope: WorkspaceScope
    ) -> WorkspaceAnalytics: ...

    def create_export(self, command: WorkspaceCommand) -> WorkspaceExport: ...

    def get_export(self, actor: UUID, export_id: UUID) -> WorkspaceExport: ...

    def export_csv(self, actor: UUID, export_id: UUID) -> bytes: ...
