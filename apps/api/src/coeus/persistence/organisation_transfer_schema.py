"""PostgreSQL schema for scheduled single-home personnel transfers."""

from collections.abc import Sequence


def organisation_transfer_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS organisation_personnel_transfers (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          reason_hash text NOT NULL CHECK (reason_hash ~ '^[0-9a-f]{64}$'),
          reason text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 500),
          actor_user_id uuid NOT NULL,
          source_membership_id uuid NOT NULL REFERENCES team_memberships(membership_id)
            ON DELETE RESTRICT,
          target_membership_id uuid NOT NULL UNIQUE,
          user_id uuid NOT NULL,
          source_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          target_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          expected_membership_version bigint NOT NULL CHECK (expected_membership_version > 0),
          expected_target_unit_version bigint NOT NULL CHECK (expected_target_unit_version > 0),
          target_role text NOT NULL,
          assignment_eligible boolean NOT NULL,
          effective_at timestamptz NOT NULL,
          source_authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id)
            ON DELETE RESTRICT,
          target_authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id)
            ON DELETE RESTRICT,
          status text NOT NULL CHECK (status IN ('pending','applied','blocked','cancelled')),
          source_result_version bigint NOT NULL CHECK (source_result_version > 0),
          target_result_version bigint NOT NULL CHECK (target_result_version >= 0),
          failure_code text NOT NULL DEFAULT '' CHECK (char_length(failure_code) <= 64),
          scheduled_at timestamptz NOT NULL,
          applied_at timestamptz,
          CONSTRAINT ck_personnel_transfer_terminal_time CHECK (
            (status = 'applied' AND applied_at IS NOT NULL) OR
            (status <> 'applied' AND applied_at IS NULL)
          )
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_personnel_transfer_pending_source
        ON organisation_personnel_transfers(source_membership_id)
        WHERE status='pending'
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_personnel_transfer_due
        ON organisation_personnel_transfers(effective_at,command_id)
        WHERE status='pending'
        """,
    )
