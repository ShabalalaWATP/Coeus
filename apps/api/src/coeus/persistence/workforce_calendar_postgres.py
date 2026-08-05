"""Serialisable PostgreSQL store for canonical workforce calendars."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.calendar_commitments import CalendarCommitment, CalendarCommitmentResponse
from coeus.domain.calendar_mutation_hash import calendar_preview_hash
from coeus.domain.calendar_occurrence_policy import validate_occurrence_request
from coeus.domain.organisation import ManagementAction
from coeus.domain.workforce_calendar import (
    CalendarEvent,
    CalendarEventStatus,
    CalendarIdempotencyConflict,
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarMutationResult,
    CalendarMutationSnapshot,
    ScopedCalendarEvent,
)
from coeus.persistence import workforce_calendar_sql as sql
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.workforce_calendar_authority import validate_calendar_authority
from coeus.persistence.workforce_calendar_commitments import (
    list_commitments,
    record_commitment_change,
    respond_commitment,
)
from coeus.persistence.workforce_calendar_evidence import append_calendar_evidence
from coeus.persistence.workforce_calendar_locks import lock_calendar_command
from coeus.persistence.workforce_calendar_occurrences import mutate_occurrence
from coeus.persistence.workforce_calendar_projection import list_unit_events
from coeus.persistence.workforce_calendar_read import get_event, list_owner_events
from coeus.persistence.workforce_calendar_rows import decode_event, event_params, event_snapshot
from coeus.persistence.workforce_calendar_scope_writes import insert_scopes


class PostgresWorkforceCalendarStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_event(self, event_id: UUID) -> CalendarEvent | None:
        return get_event(self._engine, event_id)

    def list_owner_events(
        self, owner_user_id: UUID, window_start: datetime, window_end: datetime
    ) -> tuple[CalendarEvent, ...]:
        return list_owner_events(self._engine, owner_user_id, window_start, window_end)

    def list_unit_events(
        self,
        actor_user_id: UUID,
        authorising_grant_id: UUID,
        action: ManagementAction,
        root_unit_id: UUID,
        unit_ids: tuple[UUID, ...],
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[ScopedCalendarEvent, ...]:
        return list_unit_events(
            self._engine,
            actor_user_id,
            authorising_grant_id,
            action,
            root_unit_id,
            unit_ids,
            window_start,
            window_end,
        )

    def inspect(self, request: CalendarMutationRequest) -> CalendarMutationSnapshot:
        with self._engine.begin() as connection:
            return _snapshot(connection, request)

    def replay(self, command: CalendarMutationCommand) -> CalendarMutationResult | None:
        with self._engine.begin() as connection:
            return _replay(_load_command(connection, command), command)

    def apply(self, command: CalendarMutationCommand) -> CalendarMutationResult:
        return retry_serializable_once(lambda: self._apply_once(command))

    def list_commitments(self, subject_user_id: UUID) -> tuple[CalendarCommitment, ...]:
        return list_commitments(self._engine, subject_user_id)

    def respond_commitment(self, response: CalendarCommitmentResponse) -> CalendarCommitment:
        return respond_commitment(self._engine, response)

    def _apply_once(self, command: CalendarMutationCommand) -> CalendarMutationResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            lock_calendar_command(connection, command)
            replay = _replay(_load_command(connection, command), command)
            if replay is not None:
                return replay
            occurred_at = transaction_time(connection)
            _validate_lifecycle(connection, command)
            validate_calendar_authority(connection, command, occurred_at)
            snapshot = _snapshot(connection, command.request)
            expected_hash = calendar_preview_hash(command.request, command.actor_user_id, snapshot)
            if expected_hash != command.preview_hash:
                raise CalendarMutationConflict("the calendar preview is stale")
            result, stored = _mutate(connection, command, occurred_at)
            record_commitment_change(connection, command, stored, occurred_at)
            _write_history(connection, command, stored, occurred_at)
            _write_command(connection, command, result, occurred_at)
            append_calendar_evidence(connection, command, result, occurred_at)
            return result


def _load_command(
    connection: Connection, command: CalendarMutationCommand
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(sql.LOAD_COMMAND),
            {
                "command_id": command.command_id,
                "actor_user_id": command.actor_user_id,
                "idempotency_key": command.idempotency_key,
            },
        ).mappings()
    )


def _replay(
    rows: tuple[RowMapping, ...], command: CalendarMutationCommand
) -> CalendarMutationResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise CalendarIdempotencyConflict(
            "command and idempotency key identify different calendar operations"
        )
    row = rows[0]
    request = command.request
    matches = (
        UUID(str(row["command_id"])) == command.command_id
        and UUID(str(row["actor_user_id"])) == command.actor_user_id
        and str(row["idempotency_key"]) == command.idempotency_key
        and str(row["command_type"]) == request.operation.value
        and str(row["request_hash"]) == command.preview_hash
        and UUID(str(row["event_id"])) == request.event.event_id
    )
    if not matches:
        raise CalendarIdempotencyConflict(
            "command or idempotency key is already used by another calendar operation"
        )
    return CalendarMutationResult(
        request.event.event_id,
        int(str(row["result_version"])),
        True,
        None if row["future_event_id"] is None else UUID(str(row["future_event_id"])),
    )


def _validate_lifecycle(connection: Connection, command: CalendarMutationCommand) -> None:
    request = command.request
    submitted = request.event
    row = (
        connection.execute(text(sql.GET_EVENT), {"event_id": submitted.event_id}).mappings().first()
    )
    if request.operation is CalendarMutationOperation.CREATE:
        if row is not None:
            raise CalendarMutationConflict("the calendar event already exists")
        if (
            request.expected_version != 0
            or submitted.version != 1
            or submitted.status is not CalendarEventStatus.ACTIVE
            or submitted.created_by_user_id != command.actor_user_id
        ):
            raise CalendarMutationConflict("new calendar event metadata is invalid")
        return
    if row is None:
        raise CalendarMutationConflict("the calendar event does not exist")
    current = decode_event(row)
    validate_occurrence_request(request, current)
    if request.future_event_id is not None:
        future = connection.execute(
            text(sql.GET_EVENT), {"event_id": request.future_event_id}
        ).first()
        if future is not None:
            raise CalendarMutationConflict("the future calendar series already exists")
    immutable = (
        submitted.owner_user_id,
        submitted.source,
        submitted.created_by_user_id,
        submitted.manager_scope_unit_id,
    )
    stored = (
        current.owner_user_id,
        current.source,
        current.created_by_user_id,
        current.manager_scope_unit_id,
    )
    if (
        immutable != stored
        or request.expected_version != current.version
        or submitted.version != current.version
        or current.status is not CalendarEventStatus.ACTIVE
    ):
        raise CalendarMutationConflict("the calendar event identity or version is stale")
    if (
        request.operation
        in {
            CalendarMutationOperation.UPDATE,
            CalendarMutationOperation.UPDATE_OCCURRENCE,
            CalendarMutationOperation.UPDATE_FUTURE,
        }
        and submitted.status is not CalendarEventStatus.ACTIVE
    ):
        raise CalendarMutationConflict("updates require an active event")


def _snapshot(connection: Connection, request: CalendarMutationRequest) -> CalendarMutationSnapshot:
    event = request.event
    current_row = (
        connection.execute(text(sql.GET_EVENT), {"event_id": event.event_id}).mappings().first()
    )
    current = None if current_row is None else decode_event(current_row)
    overlaps = int(connection.execute(text(sql.COUNT_OVERLAPS), event_params(event)).scalar_one())
    state = {
        "current": None if current is None else json.loads(event_snapshot(current)),
        "overlapping_events": overlaps,
    }
    digest = sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return CalendarMutationSnapshot(0 if current is None else current.version, overlaps, digest)


def _mutate(
    connection: Connection, command: CalendarMutationCommand, occurred_at: datetime
) -> tuple[CalendarMutationResult, CalendarEvent]:
    request = command.request
    if request.operation in {
        CalendarMutationOperation.UPDATE_OCCURRENCE,
        CalendarMutationOperation.CANCEL_OCCURRENCE,
        CalendarMutationOperation.UPDATE_FUTURE,
    }:
        return mutate_occurrence(connection, command, occurred_at)
    params = {
        **event_params(request.event),
        "expected_version": request.expected_version,
        "occurred_at": occurred_at,
    }
    if request.operation is CalendarMutationOperation.CREATE:
        version = connection.execute(text(sql.INSERT_EVENT), params).scalar_one_or_none()
        if version is not None:
            insert_scopes(connection, request.event, occurred_at)
    else:
        statement = (
            sql.UPDATE_EVENT
            if request.operation is CalendarMutationOperation.UPDATE
            else sql.CANCEL_EVENT
        )
        version = connection.execute(text(statement), params).scalar_one_or_none()
    if version is None:
        raise CalendarMutationConflict("the calendar event identity or version is stale")
    row = (
        connection.execute(text(sql.GET_EVENT), {"event_id": request.event.event_id})
        .mappings()
        .one()
    )
    stored = decode_event(row)
    return CalendarMutationResult(stored.event_id, int(str(version))), stored


def _write_history(
    connection: Connection,
    command: CalendarMutationCommand,
    event: CalendarEvent,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(sql.INSERT_HISTORY),
        {
            "history_id": uuid5(
                NAMESPACE_URL, f"coeus:calendar-history:{event.event_id}:{event.version}"
            ),
            "event_id": event.event_id,
            "event_version": event.version,
            "snapshot": event_snapshot(event),
            "actor_user_id": command.actor_user_id,
            "occurred_at": occurred_at,
            "reason_hash": sha256(command.request.reason.encode()).hexdigest(),
        },
    )


def _write_command(
    connection: Connection,
    command: CalendarMutationCommand,
    result: CalendarMutationResult,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(sql.INSERT_COMMAND),
        {
            "command_id": command.command_id,
            "actor_user_id": command.actor_user_id,
            "idempotency_key": command.idempotency_key,
            "command_type": command.request.operation.value,
            "request_hash": command.preview_hash,
            "event_id": result.event_id,
            "result_version": result.version,
            "future_event_id": result.future_event_id,
            "occurred_at": occurred_at,
        },
    ).one()
