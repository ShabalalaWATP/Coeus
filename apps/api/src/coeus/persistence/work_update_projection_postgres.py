"""Access-rechecked, idempotent PostgreSQL work-update projection."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.application.ports.work_update_projection import WorkUpdateProjection
from coeus.domain.organisation import ManagementAction
from coeus.domain.outbox import OutboxMessage
from coeus.domain.work_update_events import WorkUpdateEvent
from coeus.domain.workspace_productivity import WorkspaceRecordDenied, WorkUpdateKind
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.workspace_productivity_authority import (
    require_action,
    require_active_actor,
    require_update_object,
)


class PostgresWorkUpdateProjection(WorkUpdateProjection):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def project(self, message: OutboxMessage, event: WorkUpdateEvent) -> bool:
        return retry_serializable_once(lambda: self._project(message, event))

    def _project(self, message: OutboxMessage, event: WorkUpdateEvent) -> bool:
        with (
            self._engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection,
            connection.begin(),
        ):
            occurred_at = transaction_time(connection)
            try:
                require_active_actor(connection, event.recipient_user_id, lock=True)
                require_action(
                    connection,
                    event.recipient_user_id,
                    event.unit_id,
                    ManagementAction.WORK_UPDATE_VIEW,
                    occurred_at,
                )
                require_update_object(
                    connection,
                    event.recipient_user_id,
                    event.unit_id,
                    event.object_type,
                    event.object_id,
                    occurred_at,
                )
            except WorkspaceRecordDenied:
                return False
            if event.kind is WorkUpdateKind.DUE_SOON and not _due_reminders_enabled(
                connection, event.recipient_user_id
            ):
                return False
            result = connection.execute(
                text(_INSERT),
                {
                    "id": uuid5(
                        NAMESPACE_URL,
                        f"coeus:work-update:{message.event_id}:{event.recipient_user_id}",
                    ),
                    "recipient": event.recipient_user_id,
                    "event_key": f"outbox:{message.event_id}",
                    "kind": event.kind.value,
                    "unit": event.unit_id,
                    "object_type": event.object_type,
                    "object_id": event.object_id,
                    "occurred_at": message.created_at,
                },
            )
            return result.rowcount == 1


def _due_reminders_enabled(connection: Connection, recipient: UUID) -> bool:
    value = connection.execute(
        text("SELECT due_reminders FROM workspace_delivery_preferences WHERE user_id=:recipient"),
        {"recipient": recipient},
    ).scalar_one_or_none()
    return value is None or bool(value)


_INSERT = """
INSERT INTO workspace_work_updates(
 update_id,recipient_user_id,event_key,kind,unit_id,object_type,object_id,occurred_at)
VALUES (
 :id,:recipient,:event_key,:kind,:unit,:object_type,:object_id,:occurred_at)
ON CONFLICT(recipient_user_id,event_key) DO NOTHING
"""
