"""PostgreSQL schema for immutable accountable-owner handover commands."""

from collections.abc import Sequence


def work_package_handover_schema_statements() -> Sequence[str]:
    return (
        _COMMANDS,
        _INDEX,
        _IMMUTABLE_FUNCTION,
        _IMMUTABLE_TRIGGER,
    )


_COMMANDS = """
CREATE TABLE IF NOT EXISTS work_package_handover_commands (
  command_id uuid PRIMARY KEY,
  idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
  request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  preview_hash char(64) NOT NULL CHECK (preview_hash ~ '^[0-9a-f]{64}$'),
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  source_user_id uuid NOT NULL,
  target_user_id uuid NOT NULL,
  actor_user_id uuid NOT NULL,
  expected_package_version bigint NOT NULL CHECK (expected_package_version > 0),
  result_package_version bigint NOT NULL CHECK (result_package_version > 0),
  released_reservation_count integer NOT NULL CHECK (released_reservation_count >= 0),
  replacement_reservation_count integer NOT NULL CHECK (replacement_reservation_count >= 0),
  occurred_at timestamptz NOT NULL,
  UNIQUE (actor_user_id,idempotency_key),
  CHECK (source_user_id <> target_user_id)
)
"""

_INDEX = """
CREATE INDEX IF NOT EXISTS idx_work_package_handover_commands_package
ON work_package_handover_commands(package_id,occurred_at,command_id)
"""

_IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION reject_work_package_handover_command_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'work package handover commands are immutable';
END
$$
"""

_IMMUTABLE_TRIGGER = """
DROP TRIGGER IF EXISTS trg_work_package_handover_commands_immutable
ON work_package_handover_commands;
CREATE TRIGGER trg_work_package_handover_commands_immutable
BEFORE UPDATE OR DELETE ON work_package_handover_commands
FOR EACH ROW EXECUTE FUNCTION reject_work_package_handover_command_mutation()
"""
