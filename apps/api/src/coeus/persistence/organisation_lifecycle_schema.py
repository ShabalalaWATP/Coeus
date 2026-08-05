"""PostgreSQL schema for idempotent organisation lifecycle commands."""

from collections.abc import Sequence


def organisation_lifecycle_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS organisation_unit_commands (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          operation text NOT NULL CHECK (operation IN ('create','edit')),
          actor_user_id uuid NOT NULL,
          unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id)
            ON DELETE RESTRICT,
          expected_version bigint NOT NULL CHECK (expected_version > 0),
          result_version bigint NOT NULL CHECK (result_version > 0),
          topology_revision_id uuid REFERENCES organisation_topology_revisions(revision_id)
            ON DELETE RESTRICT,
          occurred_at timestamptz NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organisation_unit_commands_unit
        ON organisation_unit_commands(unit_id, occurred_at DESC)
        """,
    )
