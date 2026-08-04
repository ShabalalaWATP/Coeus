"""PostgreSQL schema for canonical workflow-leg team ownership."""

from collections.abc import Sequence


def team_task_ownership_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS team_task_ownership (
          ownership_id uuid PRIMARY KEY,
          ticket_id uuid NOT NULL,
          workflow_leg text NOT NULL CHECK (workflow_leg IN
            ('rfa','cm_collection','cm_analysis','qc')),
          owning_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id)
            ON DELETE RESTRICT,
          manager_user_id uuid,
          state text NOT NULL CHECK (state IN
            ('triage','proposed','accepted','active','completed','cancelled',
             'ownership_unresolved')),
          accepted_at timestamptz,
          target_date date,
          topology_revision_id uuid NOT NULL REFERENCES organisation_topology_revisions(revision_id)
            ON DELETE RESTRICT,
          capability_policy_version bigint NOT NULL CHECK (capability_policy_version > 0),
          version bigint NOT NULL CHECK (version > 0),
          history_reference uuid NOT NULL,
          provenance text NOT NULL CHECK (char_length(provenance) BETWEEN 1 AND 120),
          reason text NOT NULL DEFAULT '' CHECK (char_length(reason) <= 500),
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_team_task_ownership_leg UNIQUE (ticket_id, workflow_leg),
          CONSTRAINT ck_team_task_ownership_acceptance CHECK (
            (state IN ('accepted','active','completed') AND accepted_at IS NOT NULL) OR
            (state NOT IN ('accepted','active','completed') AND accepted_at IS NULL)
          )
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_team_task_ownership_unit_state
        ON team_task_ownership(owning_unit_id, state, target_date, ticket_id)
        """,
    )
