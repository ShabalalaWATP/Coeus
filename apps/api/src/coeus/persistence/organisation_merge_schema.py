"""PostgreSQL schema for explicit-disposition organisation merges."""

from collections.abc import Sequence

from coeus.persistence.organisation_merge_history_schema import (
    merge_history_schema_statements,
)
from coeus.persistence.organisation_merge_topology_schema import (
    merge_topology_guard_statement,
)


def organisation_merge_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS organisation_merge_commands (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          reason_hash text NOT NULL CHECK (reason_hash ~ '^[0-9a-f]{64}$'),
          actor_user_id uuid NOT NULL,
          source_unit_ids uuid[] NOT NULL CHECK (cardinality(source_unit_ids) >= 2),
          source_expected_versions bigint[] NOT NULL,
          source_result_versions bigint[] NOT NULL,
          successor_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id)
            ON DELETE RESTRICT,
          successor_expected_version bigint NOT NULL CHECK (successor_expected_version > 0),
          successor_result_version bigint NOT NULL CHECK (successor_result_version > 0),
          authority_map jsonb NOT NULL,
          occurred_at timestamptz NOT NULL,
          CONSTRAINT ck_organisation_merge_version_arrays CHECK (
            cardinality(source_unit_ids) = cardinality(source_expected_versions) AND
            cardinality(source_unit_ids) = cardinality(source_result_versions)
          )
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS organisation_merge_dispositions (
          command_id uuid NOT NULL REFERENCES organisation_merge_commands(command_id)
            ON DELETE RESTRICT,
          record_kind text NOT NULL CHECK (record_kind IN
            ('child_unit','membership','grant','delivery_profile','capability','task',
             'pending_transfer')),
          record_id uuid NOT NULL,
          expected_version bigint NOT NULL CHECK (expected_version > 0),
          action text NOT NULL CHECK (action IN ('move','end','revoke','cancel')),
          target_unit_id uuid REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          replacement_id uuid,
          PRIMARY KEY (command_id,record_kind,record_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS team_task_ownership_history (
          ownership_id uuid NOT NULL,
          version bigint NOT NULL CHECK (version > 0),
          ticket_id uuid NOT NULL,
          workflow_leg text NOT NULL,
          owning_unit_id uuid NOT NULL,
          manager_user_id uuid,
          state text NOT NULL,
          accepted_at timestamptz,
          target_date date,
          topology_revision_id uuid NOT NULL,
          capability_policy_version bigint NOT NULL,
          history_reference uuid NOT NULL,
          provenance text NOT NULL,
          reason text NOT NULL,
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          recorded_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
          PRIMARY KEY (ownership_id,version)
        )
        """,
        """
        CREATE OR REPLACE FUNCTION preserve_team_task_ownership_history()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        BEGIN
          INSERT INTO team_task_ownership_history(
            ownership_id,version,ticket_id,workflow_leg,owning_unit_id,manager_user_id,
            state,accepted_at,target_date,topology_revision_id,capability_policy_version,
            history_reference,provenance,reason,created_at,updated_at)
          VALUES (OLD.ownership_id,OLD.version,OLD.ticket_id,OLD.workflow_leg,
            OLD.owning_unit_id,OLD.manager_user_id,OLD.state,OLD.accepted_at,
            OLD.target_date,OLD.topology_revision_id,OLD.capability_policy_version,
            OLD.history_reference,OLD.provenance,OLD.reason,OLD.created_at,OLD.updated_at)
          ON CONFLICT (ownership_id,version) DO NOTHING;
          RETURN NEW;
        END
        $function$
        """,
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname='trg_team_task_ownership_history'
              AND tgrelid='team_task_ownership'::regclass
          ) THEN
            CREATE TRIGGER trg_team_task_ownership_history
            BEFORE UPDATE ON team_task_ownership
            FOR EACH ROW EXECUTE FUNCTION preserve_team_task_ownership_history();
          END IF;
        END
        $trigger$
        """,
        """
        CREATE OR REPLACE FUNCTION reject_team_task_ownership_history_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        BEGIN
          RAISE EXCEPTION 'team task ownership history is immutable';
        END
        $function$
        """,
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname='trg_team_task_ownership_history_immutable'
              AND tgrelid='team_task_ownership_history'::regclass
          ) THEN
            CREATE TRIGGER trg_team_task_ownership_history_immutable
            BEFORE UPDATE OR DELETE ON team_task_ownership_history
            FOR EACH ROW EXECUTE FUNCTION reject_team_task_ownership_history_mutation();
          END IF;
        END
        $trigger$
        """,
        *merge_history_schema_statements(),
        merge_topology_guard_statement(),
    )
