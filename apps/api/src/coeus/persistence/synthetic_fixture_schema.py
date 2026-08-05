"""PostgreSQL schema for idempotent synthetic fixture commands."""

from collections.abc import Sequence


def synthetic_fixture_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS synthetic_organisation_fixture_commands (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          actor_user_id uuid NOT NULL,
          manifest_version text NOT NULL
            CHECK (char_length(manifest_version) BETWEEN 1 AND 64),
          result jsonb NOT NULL,
          occurred_at timestamptz NOT NULL
        )
        """,
    )
