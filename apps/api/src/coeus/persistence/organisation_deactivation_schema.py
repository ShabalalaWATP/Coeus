"""PostgreSQL schema for idempotent organisation deactivation."""

from collections.abc import Sequence


def organisation_deactivation_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS organisation_deactivation_commands (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          reason_hash text NOT NULL CHECK (reason_hash ~ '^[0-9a-f]{64}$'),
          actor_user_id uuid NOT NULL,
          unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id)
            ON DELETE RESTRICT,
          expected_version bigint NOT NULL CHECK (expected_version > 0),
          result_version bigint NOT NULL CHECK (result_version > 0),
          occurred_at timestamptz NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organisation_deactivation_commands_unit
        ON organisation_deactivation_commands(unit_id,occurred_at DESC)
        """,
    )
