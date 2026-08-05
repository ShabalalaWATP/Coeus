"""add integrated workspace operations policy and exports

Revision ID: 20260804_0044
Revises: 20260804_0043
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260804_0044"
down_revision: str | None = "20260804_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE team_workspace_policies (
          unit_id uuid PRIMARY KEY REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          service_target_hours integer NOT NULL CHECK (service_target_hours BETWEEN 1 AND 8760),
          planning_cadence text NOT NULL
            CHECK (planning_cadence IN ('weekly','fortnightly','monthly')),
          planning_weekday smallint NOT NULL CHECK (planning_weekday BETWEEN 0 AND 6),
          planning_local_time time NOT NULL,
          planning_duration_minutes integer NOT NULL
            CHECK (
              planning_duration_minutes BETWEEN 15 AND 480
              AND planning_duration_minutes % 15 = 0
            ),
          version bigint NOT NULL CHECK (version > 0),
          updated_by_user_id uuid NOT NULL,
          updated_at timestamptz NOT NULL
        );
        CREATE TABLE workspace_export_jobs (
          export_id uuid PRIMARY KEY,
          actor_user_id uuid NOT NULL,
          unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          include_descendants boolean NOT NULL,
          authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id),
          authorising_grant_version bigint NOT NULL CHECK (authorising_grant_version > 0),
          command_id uuid NOT NULL UNIQUE,
          idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          state text NOT NULL DEFAULT 'ready' CHECK (state IN ('ready','expired')),
          row_count integer NOT NULL CHECK (row_count BETWEEN 0 AND 5000),
          snapshot_payload jsonb NOT NULL,
          handling_marking text NOT NULL CHECK (char_length(handling_marking) BETWEEN 1 AND 120),
          created_at timestamptz NOT NULL,
          expires_at timestamptz NOT NULL,
          UNIQUE(actor_user_id,idempotency_key),
          CHECK (created_at < expires_at)
        );
        CREATE INDEX idx_workspace_export_jobs_actor
        ON workspace_export_jobs(actor_user_id,created_at DESC,export_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workspace_export_jobs")
    op.execute("DROP TABLE IF EXISTS team_workspace_policies")
