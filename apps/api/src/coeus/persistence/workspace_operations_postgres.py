"""PostgreSQL implementation of integrated workspace operations."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.engine import Connection, Engine

from coeus.application.ports.workspace_operations import WorkspaceOperationsStore
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
from coeus.persistence import workspace_operations_queries as queries
from coeus.persistence.workspace_operations_exports import export_csv, get_export
from coeus.persistence.workspace_operations_writes import WorkspaceOperationsWriter


class PostgresWorkspaceOperationsStore(WorkspaceOperationsStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._writer = WorkspaceOperationsWriter(engine)

    def _read[T](self, operation: Callable[[Connection], T]) -> T:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            return operation(connection)

    def overview(self, actor: UUID, unit_id: UUID, scope: WorkspaceScope) -> WorkspaceOverview:
        return self._read(lambda connection: queries.overview(connection, actor, unit_id, scope))

    def people(
        self, actor: UUID, unit_id: UUID, scope: WorkspaceScope
    ) -> tuple[WorkspacePerson, ...]:
        return self._read(lambda connection: queries.people(connection, actor, unit_id, scope))

    def capabilities(
        self, actor: UUID, unit_id: UUID, scope: WorkspaceScope
    ) -> tuple[CapabilityCoverage, ...]:
        return self._read(
            lambda connection: queries.capabilities(connection, actor, unit_id, scope)
        )

    def policy(self, actor: UUID, unit_id: UUID) -> WorkspacePolicy:
        return self._read(lambda connection: queries.policy(connection, actor, unit_id))

    def save_policy(self, command: WorkspaceCommand) -> WorkspacePolicy:
        return self._writer.save_policy(command)

    def search(
        self, actor: UUID, unit_id: UUID, scope: WorkspaceScope, query: str, limit: int
    ) -> tuple[WorkspaceSearchResult, ...]:
        return self._read(
            lambda connection: queries.search(connection, actor, unit_id, scope, query, limit)
        )

    def analytics(self, actor: UUID, unit_id: UUID, scope: WorkspaceScope) -> WorkspaceAnalytics:
        return self._read(lambda connection: queries.analytics(connection, actor, unit_id, scope))

    def create_export(self, command: WorkspaceCommand) -> WorkspaceExport:
        return self._writer.create_export(command)

    def get_export(self, actor: UUID, export_id: UUID) -> WorkspaceExport:
        return self._read(lambda connection: get_export(connection, actor, export_id))

    def export_csv(self, actor: UUID, export_id: UUID) -> bytes:
        return self._read(lambda connection: export_csv(connection, actor, export_id))
