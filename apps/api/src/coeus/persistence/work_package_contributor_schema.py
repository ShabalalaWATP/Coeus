"""PostgreSQL schema for immutable contributor commands."""

from collections.abc import Sequence


def work_package_contributor_schema_statements() -> Sequence[str]:
    return (
        _COMMANDS,
        _PACKAGE_INDEX,
        _IMMUTABLE_FUNCTION,
        _IMMUTABLE_TRIGGER,
    )


_COMMANDS = """
CREATE TABLE IF NOT EXISTS work_package_contributor_commands (
  command_id uuid PRIMARY KEY,
  idempotency_key text NOT NULL UNIQUE CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
  request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  contributor_user_id uuid NOT NULL,
  actor_user_id uuid NOT NULL,
  operation text NOT NULL CHECK (operation IN ('add','end')),
  expected_package_version bigint NOT NULL CHECK (expected_package_version > 0),
  result_package_version bigint NOT NULL CHECK (result_package_version > 0),
  result_active boolean NOT NULL,
  occurred_at timestamptz NOT NULL,
  CHECK (
    (operation='add' AND result_active) OR
    (operation='end' AND NOT result_active)
  )
)
"""

_PACKAGE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_work_package_contributor_commands_package
ON work_package_contributor_commands(package_id,occurred_at,command_id)
"""

_IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION reject_work_package_contributor_command_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'work package contributor commands are immutable';
END
$$
"""

_IMMUTABLE_TRIGGER = """
DROP TRIGGER IF EXISTS trg_work_package_contributor_commands_immutable
ON work_package_contributor_commands;
CREATE TRIGGER trg_work_package_contributor_commands_immutable
BEFORE UPDATE OR DELETE ON work_package_contributor_commands
FOR EACH ROW EXECUTE FUNCTION reject_work_package_contributor_command_mutation()
"""
