"""Idempotent DDL for disabled organisation grant commands."""

from collections.abc import Sequence


def organisation_authority_schema_statements() -> Sequence[str]:
    return (
        "ALTER TABLE team_management_grants ADD COLUMN IF NOT EXISTS revoked_by_user_id uuid",
        "ALTER TABLE team_management_grants ADD COLUMN IF NOT EXISTS revocation_reason text "
        "NOT NULL DEFAULT '' CHECK (char_length(revocation_reason) <= 500)",
        """
        CREATE TABLE IF NOT EXISTS organisation_grant_commands (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash char(64) NOT NULL,
          command_type text NOT NULL CHECK (command_type IN ('create', 'revoke')),
          actor_user_id uuid NOT NULL,
          grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id) ON DELETE RESTRICT,
          authorising_grant_id uuid NOT NULL
            REFERENCES team_management_grants(grant_id) ON DELETE RESTRICT,
          result_version bigint NOT NULL CHECK (result_version > 0),
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organisation_grant_commands_grant
        ON organisation_grant_commands(grant_id, created_at, command_id)
        """,
        """
        CREATE OR REPLACE FUNCTION reject_organisation_grant_lineage_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        BEGIN
          IF OLD.manager_user_id IS DISTINCT FROM NEW.manager_user_id OR
             OLD.root_unit_id IS DISTINCT FROM NEW.root_unit_id OR
             OLD.action IS DISTINCT FROM NEW.action OR
             OLD.source_grant_id IS DISTINCT FROM NEW.source_grant_id OR
             OLD.delegation_depth IS DISTINCT FROM NEW.delegation_depth OR
             OLD.created_by_user_id IS DISTINCT FROM NEW.created_by_user_id OR
             OLD.valid_from IS DISTINCT FROM NEW.valid_from THEN
            RAISE EXCEPTION 'organisation grant lineage fields are immutable';
          END IF;
          RETURN NEW;
        END
        $function$
        """,
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_organisation_grant_lineage_immutable'
              AND tgrelid = 'team_management_grants'::regclass
          ) THEN
            CREATE TRIGGER trg_organisation_grant_lineage_immutable
            BEFORE UPDATE ON team_management_grants FOR EACH ROW
            EXECUTE FUNCTION reject_organisation_grant_lineage_mutation();
          END IF;
        END
        $trigger$
        """,
    )
