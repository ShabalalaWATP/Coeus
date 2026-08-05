"""Transactional subject responses and notifications for manager commitments."""

from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.domain.calendar_commitments import (
    CalendarCommitment,
    CalendarCommitmentResponse,
    CommitmentResponseState,
)
from coeus.domain.workforce_calendar import (
    CalendarEvent,
    CalendarEventSource,
    CalendarEventStatus,
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationOperation,
)
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.workforce_calendar_rows import decode_event

_LIST = """
SELECT event.*, exceptions.exception_rows, response.response_state,
 response.response_version,response.responded_at,
 COALESCE(notification.notified_at,response.updated_at) AS notified_at
FROM calendar_commitment_responses response
JOIN calendar_events event ON event.event_id=response.event_id
LEFT JOIN LATERAL (
 SELECT jsonb_agg(jsonb_build_object('occurrence_key',occurrence_key,
   'action',action,'replacement',replacement) ORDER BY occurrence_key) exception_rows
 FROM calendar_event_exceptions WHERE event_id=event.event_id
) exceptions ON TRUE
LEFT JOIN LATERAL (
 SELECT max(created_at) AS notified_at FROM calendar_commitment_notifications
 WHERE event_id=event.event_id AND recipient_user_id=response.subject_user_id
   AND notification_type IN ('created','changed','cancelled')
) notification ON TRUE
WHERE response.subject_user_id=:subject AND event.status<>'cancelled'
ORDER BY COALESCE(event.starts_at,event.all_day_start::timestamp),event.event_id LIMIT 100
"""


def list_commitments(engine: Engine, subject: UUID) -> tuple[CalendarCommitment, ...]:
    with engine.begin() as connection:
        rows = connection.execute(text(_LIST), {"subject": subject}).mappings()
        return tuple(
            CalendarCommitment(
                decode_event(row),
                CommitmentResponseState(str(row["response_state"])),
                int(str(row["response_version"])),
                row["notified_at"],
                row["responded_at"],
            )
            for row in rows
        )


def respond_commitment(engine: Engine, response: CalendarCommitmentResponse) -> CalendarCommitment:
    return retry_serializable_once(lambda: _respond_once(engine, response))


def _respond_once(engine: Engine, response: CalendarCommitmentResponse) -> CalendarCommitment:
    with engine.begin() as connection:
        connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
        now = transaction_time(connection)
        row = (
            connection.execute(
                text(
                    "SELECT response.*,event.source,event.status,event.created_by_user_id "
                    "FROM calendar_commitment_responses response JOIN calendar_events event "
                    "ON event.event_id=response.event_id WHERE response.event_id=:event FOR UPDATE"
                ),
                {"event": response.event_id},
            )
            .mappings()
            .first()
        )
        if (
            row is None
            or UUID(str(row["subject_user_id"])) != response.subject_user_id
            or row["source"] != CalendarEventSource.MANAGER.value
            or row["status"] != CalendarEventStatus.ACTIVE.value
        ):
            raise CalendarMutationConflict("the manager commitment is not available")
        updated = connection.execute(
            text(
                "UPDATE calendar_commitment_responses SET response_state=:state,"
                "response_version=response_version+1,responded_at=:now,"
                "response_reason_hash=:reason_hash,updated_at=:now "
                "WHERE event_id=:event AND response_version=:expected RETURNING response_version"
            ),
            {
                "state": response.state.value,
                "now": now,
                "reason_hash": sha256(response.reason.encode()).hexdigest()
                if response.reason
                else None,
                "event": response.event_id,
                "expected": response.expected_version,
            },
        ).scalar_one_or_none()
        if updated is None:
            raise CalendarMutationConflict("the commitment response version is stale")
        _notify(
            connection,
            response.event_id,
            UUID(str(row["created_by_user_id"])),
            response.state.value,
            now,
        )
    return next(
        item
        for item in list_commitments(engine, response.subject_user_id)
        if item.event.event_id == response.event_id
    )


def record_commitment_change(
    connection: Connection,
    command: CalendarMutationCommand,
    event: CalendarEvent,
    occurred_at: datetime,
) -> None:
    if event.source is not CalendarEventSource.MANAGER:
        return
    operation = command.request.operation
    if operation is CalendarMutationOperation.CREATE:
        connection.execute(
            text(
                "INSERT INTO calendar_commitment_responses(event_id,subject_user_id,updated_at) "
                "VALUES(:event,:subject,:now)"
            ),
            {"event": event.event_id, "subject": event.owner_user_id, "now": occurred_at},
        )
        notification_type = "created"
    elif operation in {
        CalendarMutationOperation.UPDATE,
        CalendarMutationOperation.UPDATE_OCCURRENCE,
        CalendarMutationOperation.UPDATE_FUTURE,
    }:
        connection.execute(
            text(
                "UPDATE calendar_commitment_responses SET response_state='pending',"
                "response_version=response_version+1,responded_at=NULL,response_reason_hash=NULL,"
                "updated_at=:now WHERE event_id=:event"
            ),
            {"event": event.event_id, "now": occurred_at},
        )
        notification_type = "changed"
    else:
        notification_type = "cancelled"
    _notify(connection, event.event_id, event.owner_user_id, notification_type, occurred_at)
    if command.request.future_event_id is not None:
        child_id = command.request.future_event_id
        connection.execute(
            text(
                "INSERT INTO calendar_commitment_responses(event_id,subject_user_id,updated_at) "
                "VALUES(:event,:subject,:now)"
            ),
            {"event": child_id, "subject": event.owner_user_id, "now": occurred_at},
        )
        _notify(connection, child_id, event.owner_user_id, "created", occurred_at)


def _notify(
    connection: Connection,
    event_id: UUID,
    recipient: UUID,
    notification_type: str,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(
            "INSERT INTO calendar_commitment_notifications(notification_id,event_id,"
            "recipient_user_id,notification_type,created_at) "
            "VALUES(:id,:event,:recipient,:kind,:now)"
        ),
        {
            "id": uuid4(),
            "event": event_id,
            "recipient": recipient,
            "kind": notification_type,
            "now": occurred_at,
        },
    )
