"""Bounded, access-rechecked workspace productivity queries."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation import ManagementAction
from coeus.domain.team_task_board import TeamBoardQuery, TeamTaskBoardDenied
from coeus.domain.workspace_productivity import (
    DeliveryPreferences,
    PackageTemplate,
    RecordPage,
    SavedBoardFilters,
    SavedBoardView,
    WorkspaceRecordDenied,
    WorkspaceStoreLink,
    WorkUpdate,
)
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.team_task_board_authority import resolve_board_authority
from coeus.persistence.workspace_productivity_authority import (
    require_action,
    require_active_actor,
    require_link_source,
    require_update_object,
)
from coeus.persistence.workspace_productivity_records import (
    preference_row,
    store_link_row,
    template_row,
    update_row,
    view_row,
)


def query_views(
    connection: Connection, actor: UUID, cursor: UUID | None, limit: int
) -> RecordPage[SavedBoardView]:
    require_active_actor(connection, actor)
    now = transaction_time(connection)
    rows = connection.execute(
        text(
            "SELECT * FROM workspace_saved_views WHERE owner_user_id=:actor "
            "AND (CAST(:cursor AS uuid) IS NULL OR view_id>CAST(:cursor AS uuid)) "
            "ORDER BY view_id LIMIT 501"
        ),
        {"actor": actor, "cursor": cursor},
    ).mappings()
    visible = []
    for row in rows:
        item = view_row(row)
        filters = item.filters
        try:
            require_action(connection, actor, item.unit_id, ManagementAction.WORKSPACE_VIEW, now)
            resolve_board_authority(
                connection,
                actor,
                item.unit_id,
                _board_query(filters),
                now,
            )
        except (TeamTaskBoardDenied, WorkspaceRecordDenied):
            continue
        visible.append(item)
        if len(visible) > limit:
            break
    return RecordPage(
        tuple(visible[:limit]), visible[limit - 1].view_id if len(visible) > limit else None
    )


def query_templates(
    connection: Connection, actor: UUID, unit_id: UUID, cursor: UUID | None, limit: int
) -> RecordPage[PackageTemplate]:
    require_active_actor(connection, actor)
    require_action(
        connection, actor, unit_id, ManagementAction.WORKSPACE_VIEW, transaction_time(connection)
    )
    rows = tuple(
        connection.execute(
            text(
                "SELECT * FROM team_work_templates WHERE unit_id=:unit "
                "AND (CAST(:cursor AS uuid) IS NULL OR template_id>CAST(:cursor AS uuid)) "
                "ORDER BY template_id LIMIT :take"
            ),
            {"unit": unit_id, "cursor": cursor, "take": limit + 1},
        ).mappings()
    )
    items = tuple(template_row(row) for row in rows[:limit])
    return RecordPage(items, items[-1].template_id if len(rows) > limit else None)


def query_updates(
    connection: Connection,
    actor: UUID,
    cursor: UUID | None,
    limit: int,
    unacknowledged_only: bool,
) -> RecordPage[WorkUpdate]:
    require_active_actor(connection, actor)
    now = transaction_time(connection)
    rows = connection.execute(
        text(
            "SELECT * FROM workspace_work_updates WHERE recipient_user_id=:actor "
            "AND (CAST(:cursor AS uuid) IS NULL OR update_id>CAST(:cursor AS uuid)) "
            "AND (NOT :unacknowledged OR acknowledged_at IS NULL) ORDER BY update_id LIMIT 501"
        ),
        {"actor": actor, "cursor": cursor, "unacknowledged": unacknowledged_only},
    ).mappings()
    visible = []
    for row in rows:
        item = update_row(row)
        try:
            require_action(connection, actor, item.unit_id, ManagementAction.WORK_UPDATE_VIEW, now)
            require_update_object(
                connection, actor, item.unit_id, item.object_type, item.object_id, now
            )
        except WorkspaceRecordDenied:
            continue
        visible.append(item)
        if len(visible) > limit:
            break
    return RecordPage(
        tuple(visible[:limit]), visible[limit - 1].update_id if len(visible) > limit else None
    )


def query_preferences(connection: Connection, actor: UUID) -> DeliveryPreferences:
    require_active_actor(connection, actor)
    row = (
        connection.execute(
            text("SELECT * FROM workspace_delivery_preferences WHERE user_id=:actor"),
            {"actor": actor},
        )
        .mappings()
        .first()
    )
    if row is None:
        from coeus.domain.workspace_productivity import DeliveryMode

        return DeliveryPreferences(actor, DeliveryMode.IMMEDIATE, True, 0)
    return preference_row(row)


def query_store_links(
    connection: Connection,
    actor: UUID,
    unit_id: UUID,
    source_type: str,
    source_id: UUID,
    cursor: UUID | None,
    limit: int,
) -> RecordPage[WorkspaceStoreLink]:
    require_active_actor(connection, actor)
    require_link_source(
        connection, actor, unit_id, source_type, source_id, transaction_time(connection)
    )
    rows = tuple(
        connection.execute(
            text(
                "SELECT * FROM workspace_store_links WHERE unit_id=:unit "
                "AND source_type=:source_type AND source_id=:source_id "
                "AND (CAST(:cursor AS uuid) IS NULL OR link_id>CAST(:cursor AS uuid)) "
                "ORDER BY link_id LIMIT :take"
            ),
            {
                "unit": unit_id,
                "source_type": source_type,
                "source_id": source_id,
                "cursor": cursor,
                "take": limit + 1,
            },
        ).mappings()
    )
    items = tuple(store_link_row(row) for row in rows[:limit])
    return RecordPage(items, items[-1].link_id if len(rows) > limit else None)


def _board_query(filters: SavedBoardFilters) -> TeamBoardQuery:
    return TeamBoardQuery(
        scope=filters.scope,
        include_completed=filters.include_completed,
        columns=filters.columns,
        unit_ids=filters.unit_ids,
        priority=filters.priority,
        due_from=filters.due_from,
        due_to=filters.due_to,
    )
