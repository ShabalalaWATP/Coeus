"""Collision and authority inspection for legacy-calendar candidates."""

import json
from hashlib import sha256

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.calendar_import import (
    CalendarImportFinding,
    CalendarImportInspection,
    LegacyCalendarCandidate,
)


def inspect_calendar_import(
    connection: Connection, candidates: tuple[LegacyCalendarCandidate, ...]
) -> CalendarImportInspection:
    importable: list[LegacyCalendarCandidate] = []
    findings: list[CalendarImportFinding] = []
    existing = 0
    facts: list[dict[str, object]] = []
    for candidate in candidates:
        row = connection.execute(text(_INSPECT), _params(candidate)).mappings().one()
        codes = _finding_codes(row)
        matched = bool(row["exact_replay"])
        if codes:
            findings.extend(
                CalendarImportFinding(code, candidate.legacy_entry_id) for code in codes
            )
        elif matched:
            existing += 1
        else:
            importable.append(candidate)
        facts.append(
            {
                "entry": str(candidate.legacy_entry_id),
                "codes": codes,
                "exact_replay": matched,
                "event_present": bool(row["event_present"]),
                "record_present": bool(row["record_present"]),
            }
        )
    state_digest = sha256(
        json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return CalendarImportInspection(
        state_digest,
        tuple(importable),
        existing,
        tuple(findings),
    )


def _finding_codes(row: object) -> tuple[str, ...]:
    values = row  # RowMapping at runtime, kept generic for narrow unit fakes.
    codes: list[str] = []
    if not values["owner_active"]:  # type: ignore[index]
        codes.append("owner_account_missing")
    if not values["creator_present"]:  # type: ignore[index]
        codes.append("creator_account_missing")
    if not values["team_active"]:  # type: ignore[index]
        codes.append("team_scope_missing")
    if not values["owner_member"]:  # type: ignore[index]
        codes.append("owner_not_team_member")
    if values["identity_collision"] and not values["exact_replay"]:  # type: ignore[index]
        codes.append("canonical_identity_collision")
    if values["event_present"] and not values["exact_replay"]:  # type: ignore[index]
        codes.append("canonical_event_collision")
    if values["record_present"] and not values["exact_replay"]:  # type: ignore[index]
        codes.append("legacy_provenance_collision")
    return tuple(codes)


def _params(candidate: LegacyCalendarCandidate) -> dict[str, object]:
    return {
        "entry_id": candidate.legacy_entry_id,
        "event_id": candidate.event_id,
        "scope_id": candidate.scope_id,
        "history_id": candidate.history_id,
        "calendar_command_id": candidate.calendar_command_id,
        "team_id": candidate.team_id,
        "owner_id": candidate.owner_user_id,
        "creator_id": candidate.creator_user_id,
        "start": candidate.all_day_start,
        "end": candidate.all_day_end,
        "activity": candidate.activity.value,
        "availability": candidate.availability.value,
        "note": candidate.note,
        "calendar_idempotency": f"legacy-calendar-import-v1-{candidate.legacy_entry_id}",
    }


_INSPECT = """
SELECT
  event.event_id IS NOT NULL AS event_present,
  record.legacy_entry_id IS NOT NULL AS record_present,
  EXISTS(SELECT 1 FROM identity_account_projection account
         WHERE account.user_id=:owner_id AND account.is_active) AS owner_active,
  EXISTS(SELECT 1 FROM identity_account_projection account
         WHERE account.user_id=:creator_id) AS creator_present,
  EXISTS(SELECT 1 FROM organisation_units unit
         WHERE unit.unit_id=:team_id AND unit.is_active
           AND unit.valid_from<=:start
           AND (unit.valid_until IS NULL OR :start<unit.valid_until)) AS team_active,
  EXISTS(SELECT 1 FROM team_memberships membership
         WHERE membership.unit_id=:team_id AND membership.user_id=:owner_id
           AND membership.state='active' AND membership.valid_from<=:start
           AND (membership.valid_until IS NULL OR :start<membership.valid_until)) AS owner_member,
  (EXISTS(SELECT 1 FROM calendar_event_scopes WHERE scope_id=:scope_id)
   OR EXISTS(SELECT 1 FROM calendar_event_versions WHERE history_id=:history_id)
   OR EXISTS(SELECT 1 FROM calendar_event_commands command
             WHERE command.command_id=:calendar_command_id
                OR (command.actor_user_id=:creator_id
                    AND command.idempotency_key=:calendar_idempotency))) AS identity_collision,
  (record.legacy_entry_id=:entry_id AND record.event_id=:event_id
   AND record.team_id=:team_id AND record.owner_user_id=:owner_id
   AND record.creator_user_id=:creator_id AND event.source='legacy'
   AND event.provenance='legacy_import' AND event.owner_user_id=:owner_id
   AND event.created_by_user_id=:creator_id AND event.all_day_start=:start
   AND event.all_day_end=:end AND event.activity_category=:activity
   AND event.availability_effect=:availability AND event.note=:note
   AND event.status='active'
   AND EXISTS(SELECT 1 FROM calendar_event_scopes scope
              WHERE scope.scope_id=:scope_id AND scope.event_id=:event_id
                AND scope.scope_type='team_participant'
                AND scope.subject_user_id=:owner_id AND scope.unit_id=:team_id)
   AND EXISTS(SELECT 1 FROM calendar_event_versions history
              WHERE history.history_id=:history_id AND history.event_id=:event_id)
   AND EXISTS(SELECT 1 FROM calendar_event_commands command
              WHERE command.command_id=:calendar_command_id
                AND command.event_id=:event_id)) AS exact_replay
FROM (SELECT 1) seed
LEFT JOIN calendar_events event ON event.event_id=:event_id
LEFT JOIN calendar_legacy_import_records record ON record.legacy_entry_id=:entry_id
"""
