"""Bounded source-to-target visibility snapshots for cutover."""

import json
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.cutover_activation import CutoverSlice
from coeus.domain.teams import OrgTeam, TeamCalendarEntry, team_member_ids
from coeus.domain.tickets import TicketRecord
from coeus.persistence.codec import decode_value

SCHEMA_HEAD = "20260804_0045"
_MAX_ROWS = 100_000


@dataclass(frozen=True)
class CutoverSnapshot:
    source_hash: str
    target_hash: str
    visibility_hash: str
    source_count: int
    target_count: int
    parity: bool


def capture_snapshot(connection: Connection, slice: CutoverSlice) -> CutoverSnapshot:
    source_rows, target_rows = _CAPTURE[slice](connection)
    if len(source_rows) > _MAX_ROWS or len(target_rows) > _MAX_ROWS:
        raise ValueError("cutover visibility projection exceeds the safe row bound")
    source_hash, target_hash = _hash(source_rows), _hash(target_rows)
    return CutoverSnapshot(
        source_hash,
        target_hash,
        source_hash,
        len(source_rows),
        len(target_rows),
        source_rows == target_rows,
    )


def require_current_schema(connection: Connection) -> None:
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    if revision != SCHEMA_HEAD:
        raise ValueError("cutover candidate does not target the current schema head")


def require_no_blocking_drift(connection: Connection) -> None:
    values = connection.execute(text(_BLOCKERS)).mappings().one()
    if any(int(value) for value in values.values()):
        raise ValueError("cutover evidence has blocking relational drift")


def lock_active_administrator(connection: Connection, actor_user_id: object) -> None:
    row = (
        connection.execute(
            text(
                "SELECT is_active,roles FROM identity_account_projection "
                "WHERE user_id=:actor FOR SHARE"
            ),
            {"actor": actor_user_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None or not row["is_active"] or "Administrator" not in tuple(row["roles"]):
        raise PermissionError("an active human administrator is required")


def _organisation(connection: Connection) -> tuple[tuple[str, ...], tuple[str, ...]]:
    teams = _decoded_items(connection, "teams", OrgTeam)
    source = tuple(
        sorted(
            f"{team.team_id}|{user_id}"
            for team in teams
            if team.is_active
            for user_id in team_member_ids(team)
        )
    )
    ids = {str(team.team_id) for team in teams if team.is_active}
    target = tuple(
        sorted(
            f"{row.unit_id}|{row.user_id}"
            for row in connection.execute(text(_ORGANISATION_TARGET))
            if str(row.unit_id) in ids
        )
    )
    return source, target


def _calendar(connection: Connection) -> tuple[tuple[str, ...], tuple[str, ...]]:
    entries = _decoded_items(connection, "team_calendar", TeamCalendarEntry)
    source = tuple(sorted(f"{item.entry_id}|{item.team_id}|{item.user_id}" for item in entries))
    ids = {str(item.entry_id) for item in entries}
    target = tuple(
        sorted(
            f"{row.legacy_entry_id}|{row.team_id}|{row.owner_user_id}"
            for row in connection.execute(text(_CALENDAR_TARGET))
            if str(row.legacy_entry_id) in ids
        )
    )
    return source, target


def _task_capacity(connection: Connection) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tickets = _ticket_rows(connection)
    source = tuple(
        sorted(
            f"{ticket.ticket_id}|{assignment.route.value}|{assignment.team_id}|"
            f"{assignment.analyst_user_id}"
            for ticket in tickets
            for assignment in ticket.analyst_assignments
            if assignment.active and assignment.team_id is not None
        )
    )
    ticket_ids = {str(ticket.ticket_id) for ticket in tickets}
    target = tuple(
        sorted(
            f"{row.ticket_id}|{row.route}|{row.owning_unit_id}|{row.accountable_user_id}"
            for row in connection.execute(text(_TASK_TARGET))
            if str(row.ticket_id) in ticket_ids
        )
    )
    return source, target


def _decoded_items[T](connection: Connection, namespace: str, expected: type[T]) -> tuple[T, ...]:
    payload = connection.execute(
        text("SELECT payload FROM coeus_state WHERE namespace=:namespace"),
        {"namespace": namespace},
    ).scalar_one_or_none()
    if payload is None:
        return ()
    items = tuple(decode_value(item) for item in payload.get("items", ()))
    if any(not isinstance(item, expected) for item in items):
        raise ValueError("legacy visibility source has an invalid record type")
    return items


def _ticket_rows(connection: Connection) -> tuple[TicketRecord, ...]:
    values = tuple(
        decode_value(row.payload)
        for row in connection.execute(
            text("SELECT payload FROM coeus_ticket_aggregates ORDER BY ticket_id")
        )
    )
    if any(not isinstance(value, TicketRecord) for value in values):
        raise ValueError("ticket visibility source has an invalid record type")
    return values


def _hash(rows: tuple[str, ...]) -> str:
    return sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


_CAPTURE = {
    CutoverSlice.ORGANISATION: _organisation,
    CutoverSlice.CALENDAR: _calendar,
    CutoverSlice.TASK_CAPACITY: _task_capacity,
}

_ORGANISATION_TARGET = """
SELECT membership.unit_id,membership.user_id
FROM team_memberships membership JOIN organisation_units unit USING (unit_id)
WHERE unit.is_active AND membership.state='active'
  AND membership.valid_from<=transaction_timestamp()
  AND (membership.valid_until IS NULL OR transaction_timestamp()<membership.valid_until)
ORDER BY membership.unit_id,membership.user_id
"""

_CALENDAR_TARGET = """
SELECT record.legacy_entry_id,record.team_id,record.owner_user_id
FROM calendar_legacy_import_records record
JOIN calendar_events event ON event.event_id=record.event_id AND event.status='active'
JOIN calendar_event_scopes scope ON scope.event_id=event.event_id
  AND scope.scope_type='team_participant' AND scope.unit_id=record.team_id
  AND scope.subject_user_id=record.owner_user_id
ORDER BY record.legacy_entry_id
"""

_TASK_TARGET = """
SELECT ownership.ticket_id,
       CASE WHEN ownership.workflow_leg='rfa' THEN 'rfa'
            WHEN ownership.workflow_leg IN ('cm_collection','cm_analysis') THEN 'cm'
            ELSE ownership.workflow_leg END AS route,
       ownership.owning_unit_id,
       package.accountable_user_id
FROM team_task_ownership ownership
JOIN canonical_work_packages package ON package.ticket_id=ownership.ticket_id
 AND package.workflow_leg=ownership.workflow_leg
WHERE ownership.state NOT IN ('cancelled','ownership_unresolved')
  AND package.state NOT IN ('complete','cancelled')
  AND package.accountable_user_id IS NOT NULL
ORDER BY ownership.ticket_id,ownership.workflow_leg
"""

_BLOCKERS = """
SELECT
 (SELECT count(*) FROM organisation_reconciliation_findings
   WHERE severity='blocking' AND resolved_at IS NULL) AS reconciliation,
 (SELECT count(*) FROM team_task_ownership WHERE state='ownership_unresolved') AS ownership,
 (SELECT count(*) FROM canonical_work_packages package
   LEFT JOIN organisation_units unit ON unit.unit_id=package.owning_unit_id
   WHERE unit.unit_id IS NULL OR NOT unit.is_active) AS packages,
 (SELECT count(*) FROM capacity_reservations reservation
   LEFT JOIN canonical_work_packages package ON package.package_id=reservation.package_id
   WHERE reservation.state IN ('held','active') AND
     (package.package_id IS NULL OR package.state IN ('complete','cancelled'))) AS reservations
"""
