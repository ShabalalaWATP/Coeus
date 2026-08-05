"""PostgreSQL schema for explicit legacy-calendar import evidence."""

from collections.abc import Sequence


def calendar_import_schema_statements() -> Sequence[str]:
    return (_COMMANDS, _RECORDS, _INDEX, _IMMUTABLE_FUNCTION, _COMMAND_TRIGGER, _RECORD_TRIGGER)


_COMMANDS = """
CREATE TABLE calendar_import_commands (
  command_id uuid PRIMARY KEY,
  actor_user_id uuid NOT NULL,
  idempotency_key varchar(128) NOT NULL,
  request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  preview_hash char(64) NOT NULL CHECK (preview_hash ~ '^[0-9a-f]{64}$'),
  source_digest char(64) NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
  imported_count integer NOT NULL CHECK (imported_count >= 0),
  existing_count integer NOT NULL CHECK (existing_count >= 0),
  occurred_at timestamptz NOT NULL,
  UNIQUE(actor_user_id,idempotency_key)
)
"""

_RECORDS = """
CREATE TABLE calendar_legacy_import_records (
  legacy_entry_id uuid PRIMARY KEY,
  event_id uuid NOT NULL UNIQUE REFERENCES calendar_events(event_id) ON DELETE RESTRICT,
  team_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  owner_user_id uuid NOT NULL,
  creator_user_id uuid NOT NULL,
  source_digest char(64) NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
  command_id uuid NOT NULL REFERENCES calendar_import_commands(command_id) ON DELETE RESTRICT,
  imported_at timestamptz NOT NULL
)
"""

_INDEX = """
CREATE INDEX idx_calendar_legacy_import_records_team
ON calendar_legacy_import_records(team_id,event_id)
"""

_IMMUTABLE_FUNCTION = """
CREATE FUNCTION reject_calendar_import_evidence_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'calendar import evidence is immutable';
END;
$$ LANGUAGE plpgsql
"""

_COMMAND_TRIGGER = """
CREATE TRIGGER trg_calendar_import_commands_immutable
BEFORE UPDATE OR DELETE ON calendar_import_commands
FOR EACH ROW EXECUTE FUNCTION reject_calendar_import_evidence_mutation()
"""

_RECORD_TRIGGER = """
CREATE TRIGGER trg_calendar_import_records_immutable
BEFORE UPDATE OR DELETE ON calendar_legacy_import_records
FOR EACH ROW EXECUTE FUNCTION reject_calendar_import_evidence_mutation()
"""
