"""Canonical work-package, dependency and capacity-reservation schema."""

from collections.abc import Sequence


def work_package_schema_statements() -> Sequence[str]:
    return (
        _WORKING_PATTERNS,
        _CAPACITY_EXCEPTIONS,
        _WORK_PACKAGES,
        _PARTICIPANTS,
        _DEPENDENCIES,
        _RESERVATIONS,
        _HISTORY,
        _COMMANDS,
        _TEAM_INDEX,
        _OWNER_INDEX,
        _RESERVATION_INDEX,
        _IMMUTABLE_FUNCTION,
        _IMMUTABLE_TRIGGER,
    )


_WORKING_PATTERNS = """
CREATE TABLE IF NOT EXISTS working_patterns (
  pattern_id uuid PRIMARY KEY,
  user_id uuid NOT NULL,
  time_zone text NOT NULL CHECK (char_length(time_zone) BETWEEN 1 AND 64),
  monday_minutes integer NOT NULL CHECK (monday_minutes BETWEEN 0 AND 1440),
  tuesday_minutes integer NOT NULL CHECK (tuesday_minutes BETWEEN 0 AND 1440),
  wednesday_minutes integer NOT NULL CHECK (wednesday_minutes BETWEEN 0 AND 1440),
  thursday_minutes integer NOT NULL CHECK (thursday_minutes BETWEEN 0 AND 1440),
  friday_minutes integer NOT NULL CHECK (friday_minutes BETWEEN 0 AND 1440),
  saturday_minutes integer NOT NULL CHECK (saturday_minutes BETWEEN 0 AND 1440),
  sunday_minutes integer NOT NULL CHECK (sunday_minutes BETWEEN 0 AND 1440),
  valid_from timestamptz NOT NULL,
  valid_until timestamptz,
  version bigint NOT NULL CHECK (version > 0),
  provenance text NOT NULL CHECK (char_length(provenance) BETWEEN 1 AND 120),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  CHECK (valid_until IS NULL OR valid_from < valid_until),
  EXCLUDE USING gist (
    user_id WITH =, tstzrange(valid_from, valid_until, '[)') WITH &&
  )
)
"""

_CAPACITY_EXCEPTIONS = """
CREATE TABLE IF NOT EXISTS capacity_exceptions (
  exception_id uuid PRIMARY KEY,
  user_id uuid NOT NULL,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  reduction_minutes integer CHECK (reduction_minutes > 0),
  reduction_percent numeric(5,2) CHECK (reduction_percent > 0 AND reduction_percent <= 100),
  reason_code text NOT NULL CHECK (char_length(reason_code) BETWEEN 1 AND 80),
  note text NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
  approved_by_user_id uuid NOT NULL,
  version bigint NOT NULL CHECK (version > 0),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  CHECK (starts_at < ends_at),
  CHECK ((reduction_minutes IS NULL) <> (reduction_percent IS NULL))
)
"""


_WORK_PACKAGES = """
CREATE TABLE IF NOT EXISTS canonical_work_packages (
  package_id uuid PRIMARY KEY,
  ticket_id uuid NOT NULL,
  workflow_leg text NOT NULL CHECK (workflow_leg IN
    ('rfa','cm_collection','cm_analysis','qc')),
  owning_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  accountable_user_id uuid,
  title text NOT NULL CHECK (char_length(title) BETWEEN 3 AND 180),
  state text NOT NULL CHECK (state IN
    ('pending','ready','in_progress','blocked','complete','cancelled')),
  estimated_minutes integer CHECK (estimated_minutes > 0 AND estimated_minutes % 15 = 0),
  remaining_minutes integer CHECK (remaining_minutes >= 0 AND remaining_minutes % 15 = 0),
  due_at timestamptz,
  priority smallint CHECK (priority BETWEEN 1 AND 5),
  priority_override_reason text NOT NULL DEFAULT ''
    CHECK (char_length(priority_override_reason) <= 500),
  blocked_code text CHECK (char_length(blocked_code) BETWEEN 1 AND 80),
  blocked_note text NOT NULL DEFAULT '' CHECK (char_length(blocked_note) <= 1000),
  review_at timestamptz,
  sort_order integer NOT NULL CHECK (sort_order >= 0),
  version bigint NOT NULL CHECK (version > 0),
  provenance text NOT NULL CHECK (char_length(provenance) BETWEEN 1 AND 120),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  CONSTRAINT uq_canonical_work_package_order UNIQUE (ticket_id, workflow_leg, sort_order),
  CONSTRAINT ck_canonical_work_package_effort CHECK (
    estimated_minutes IS NULL OR
    (remaining_minutes IS NOT NULL AND remaining_minutes <= estimated_minutes)
  ),
  CONSTRAINT ck_canonical_work_package_blocked CHECK (
    (state = 'blocked' AND blocked_code IS NOT NULL AND review_at IS NOT NULL) OR
    (state <> 'blocked' AND blocked_code IS NULL AND blocked_note = '' AND review_at IS NULL)
  ),
  CONSTRAINT ck_canonical_work_package_owner CHECK (
    state IN ('pending','cancelled') OR accountable_user_id IS NOT NULL
  )
)
"""

_PARTICIPANTS = """
CREATE TABLE IF NOT EXISTS work_package_participants (
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  user_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('accountable','contributor')),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL,
  ended_at timestamptz,
  PRIMARY KEY (package_id, user_id, role),
  CONSTRAINT ck_work_package_participant_interval CHECK (
    (active AND ended_at IS NULL) OR (NOT active AND ended_at IS NOT NULL)
  )
)
"""

_DEPENDENCIES = """
CREATE TABLE IF NOT EXISTS work_package_dependencies (
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  predecessor_package_id uuid NOT NULL
    REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  created_by_user_id uuid NOT NULL,
  created_at timestamptz NOT NULL,
  PRIMARY KEY (package_id, predecessor_package_id),
  CONSTRAINT ck_work_package_dependency_not_self CHECK (package_id <> predecessor_package_id)
)
"""

_RESERVATIONS = """
CREATE TABLE IF NOT EXISTS capacity_reservations (
  reservation_id uuid PRIMARY KEY,
  user_id uuid NOT NULL,
  ticket_id uuid NOT NULL,
  workflow_leg text NOT NULL CHECK (workflow_leg IN
    ('rfa','cm_collection','cm_analysis','qc')),
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  reserved_minutes integer NOT NULL CHECK (reserved_minutes > 0 AND reserved_minutes % 15 = 0),
  state text NOT NULL CHECK (state IN ('held','active','released','expired','cancelled')),
  expires_at timestamptz,
  idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
  request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  actor_user_id uuid NOT NULL,
  version bigint NOT NULL CHECK (version > 0),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  CONSTRAINT ck_capacity_reservation_interval CHECK (starts_at < ends_at),
  CONSTRAINT ck_capacity_reservation_expiry CHECK (expires_at IS NULL OR created_at < expires_at),
  CONSTRAINT uq_capacity_reservation_actor_key UNIQUE (actor_user_id, idempotency_key)
)
"""

_HISTORY = """
CREATE TABLE IF NOT EXISTS work_package_history (
  history_id uuid PRIMARY KEY,
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  version bigint NOT NULL CHECK (version > 0),
  actor_user_id uuid NOT NULL,
  event_type text NOT NULL CHECK (char_length(event_type) BETWEEN 1 AND 80),
  evidence jsonb NOT NULL,
  occurred_at timestamptz NOT NULL,
  UNIQUE (package_id, version)
)
"""

_COMMANDS = """
CREATE TABLE IF NOT EXISTS work_package_commands (
  command_id uuid PRIMARY KEY,
  idempotency_key text NOT NULL UNIQUE CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
  request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  actor_user_id uuid NOT NULL,
  expected_version bigint NOT NULL CHECK (expected_version >= 0),
  result_version bigint NOT NULL CHECK (result_version > 0),
  operation text NOT NULL CHECK (operation IN
    ('create','update','assign','block','complete','cancel','add_dependency','remove_dependency')),
  occurred_at timestamptz NOT NULL
)
"""

_TEAM_INDEX = """
CREATE INDEX IF NOT EXISTS idx_canonical_work_packages_team_state
ON canonical_work_packages(owning_unit_id, state, due_at, ticket_id)
"""

_OWNER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_canonical_work_packages_owner_state
ON canonical_work_packages(accountable_user_id, state, due_at)
"""

_RESERVATION_INDEX = """
CREATE INDEX IF NOT EXISTS idx_capacity_reservations_user_interval
ON capacity_reservations(user_id, starts_at, ends_at)
WHERE state IN ('held','active')
"""

_IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION reject_work_package_history_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'work package history is immutable';
END
$$
"""

_IMMUTABLE_TRIGGER = """
DROP TRIGGER IF EXISTS trg_work_package_history_immutable ON work_package_history;
CREATE TRIGGER trg_work_package_history_immutable
BEFORE UPDATE OR DELETE ON work_package_history
FOR EACH ROW EXECUTE FUNCTION reject_work_package_history_mutation()
"""
