"""Transactional workspace productivity store."""

from uuid import UUID

from sqlalchemy.engine import Engine

from coeus.application.ports.workspace_productivity import WorkspaceProductivityStore
from coeus.domain.workspace_productivity import (
    DeliveryPreferences,
    PackageTemplate,
    ProductivityCommand,
    RecordPage,
    SavedBoardView,
    WorkspaceStoreLink,
    WorkUpdate,
)
from coeus.persistence.workspace_productivity_queries import (
    query_preferences,
    query_store_links,
    query_templates,
    query_updates,
    query_views,
)
from coeus.persistence.workspace_productivity_writes import WorkspaceProductivityWriter


class PostgresWorkspaceProductivityStore(WorkspaceProductivityStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._writer = WorkspaceProductivityWriter(engine)

    def list_views(
        self, actor: UUID, cursor: UUID | None, limit: int
    ) -> RecordPage[SavedBoardView]:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            return query_views(connection, actor, cursor, limit)

    def save_view(self, command: ProductivityCommand) -> SavedBoardView:
        return self._writer.save_view(command)

    def delete_view(self, command: ProductivityCommand) -> bool:
        return self._writer.delete_view(command)

    def list_templates(
        self, actor: UUID, unit_id: UUID, cursor: UUID | None, limit: int
    ) -> RecordPage[PackageTemplate]:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            return query_templates(connection, actor, unit_id, cursor, limit)

    def save_template(self, command: ProductivityCommand) -> PackageTemplate:
        return self._writer.save_template(command)

    def delete_template(self, command: ProductivityCommand) -> bool:
        return self._writer.delete_template(command)

    def deliver_update(self, command: ProductivityCommand) -> WorkUpdate:
        return self._writer.deliver_update(command)

    def list_updates(
        self, actor: UUID, cursor: UUID | None, limit: int, unacknowledged_only: bool
    ) -> RecordPage[WorkUpdate]:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            return query_updates(connection, actor, cursor, limit, unacknowledged_only)

    def acknowledge_update(self, command: ProductivityCommand) -> WorkUpdate:
        return self._writer.acknowledge_update(command)

    def get_preferences(self, actor: UUID) -> DeliveryPreferences:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            return query_preferences(connection, actor)

    def save_preferences(self, command: ProductivityCommand) -> DeliveryPreferences:
        return self._writer.save_preferences(command)

    def list_store_links(
        self,
        actor: UUID,
        unit_id: UUID,
        source_type: str,
        source_id: UUID,
        cursor: UUID | None,
        limit: int,
    ) -> RecordPage[WorkspaceStoreLink]:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            return query_store_links(
                connection, actor, unit_id, source_type, source_id, cursor, limit
            )

    def save_store_link(self, command: ProductivityCommand) -> WorkspaceStoreLink:
        return self._writer.save_store_link(command)

    def delete_store_link(self, command: ProductivityCommand) -> bool:
        return self._writer.delete_store_link(command)
