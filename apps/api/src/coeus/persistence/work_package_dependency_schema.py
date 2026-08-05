"""PostgreSQL schema for immutable dependency command evidence."""

from collections.abc import Sequence


def work_package_dependency_schema_statements() -> Sequence[str]:
    return (_COMMANDS, _INDEX, _IMMUTABLE_FUNCTION, _IMMUTABLE_TRIGGER)


_COMMANDS = """
CREATE TABLE work_package_dependency_commands (
  command_id uuid PRIMARY KEY,
  idempotency_key text NOT NULL UNIQUE CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
  request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  predecessor_package_id uuid NOT NULL
    REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  actor_user_id uuid NOT NULL,
  operation text NOT NULL CHECK (operation IN ('add','remove')),
  expected_package_version bigint NOT NULL CHECK (expected_package_version > 0),
  expected_predecessor_version bigint NOT NULL CHECK (expected_predecessor_version > 0),
  expected_ownership_version bigint NOT NULL CHECK (expected_ownership_version > 0),
  expected_grant_version bigint NOT NULL CHECK (expected_grant_version > 0),
  result_package_version bigint NOT NULL CHECK (result_package_version > 0),
  result_active boolean NOT NULL,
  occurred_at timestamptz NOT NULL,
  CHECK (package_id <> predecessor_package_id),
  CHECK ((operation='add' AND result_active) OR
         (operation='remove' AND NOT result_active))
)
"""

_INDEX = """
CREATE INDEX idx_work_package_dependency_commands_package
ON work_package_dependency_commands(package_id,occurred_at,command_id)
"""

_IMMUTABLE_FUNCTION = """
CREATE FUNCTION reject_work_package_dependency_command_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'work package dependency commands are immutable';
END
$$
"""

_IMMUTABLE_TRIGGER = """
CREATE TRIGGER trg_work_package_dependency_commands_immutable
BEFORE UPDATE OR DELETE ON work_package_dependency_commands
FOR EACH ROW EXECUTE FUNCTION reject_work_package_dependency_command_mutation()
"""
