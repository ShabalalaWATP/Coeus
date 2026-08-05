"""PostgreSQL schema for idempotent membership lifecycle commands."""

from collections.abc import Sequence


def organisation_membership_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS organisation_membership_commands (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          reason_hash text NOT NULL CHECK (reason_hash ~ '^[0-9a-f]{64}$'),
          operation text NOT NULL CHECK (operation IN ('create','update','end')),
          actor_user_id uuid NOT NULL,
          membership_id uuid NOT NULL REFERENCES team_memberships(membership_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          user_id uuid NOT NULL,
          unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id)
            ON DELETE RESTRICT,
          expected_version bigint NOT NULL CHECK (expected_version >= 0),
          result_version bigint NOT NULL CHECK (result_version > 0),
          role text NOT NULL,
          assignment_eligible boolean NOT NULL,
          valid_from timestamptz NOT NULL,
          valid_until timestamptz,
          occurred_at timestamptz NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organisation_membership_commands_membership
        ON organisation_membership_commands(membership_id, occurred_at DESC)
        """,
    )
