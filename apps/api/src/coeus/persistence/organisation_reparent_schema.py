"""PostgreSQL schema for idempotent organisation reparent commands."""

from collections.abc import Sequence


def organisation_reparent_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS organisation_reparent_commands (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          reason_hash text NOT NULL CHECK (reason_hash ~ '^[0-9a-f]{64}$'),
          actor_user_id uuid NOT NULL,
          unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          source_parent_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id)
            ON DELETE RESTRICT,
          new_parent_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id)
            ON DELETE RESTRICT,
          authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id)
            ON DELETE RESTRICT,
          expected_unit_version bigint NOT NULL CHECK (expected_unit_version > 0),
          expected_parent_version bigint NOT NULL CHECK (expected_parent_version > 0),
          result_version bigint NOT NULL CHECK (result_version > 0),
          topology_revision_id uuid NOT NULL REFERENCES organisation_topology_revisions(revision_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          occurred_at timestamptz NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organisation_reparent_commands_unit
        ON organisation_reparent_commands(unit_id, occurred_at DESC)
        """,
        """
        CREATE OR REPLACE FUNCTION validate_organisation_closure_write()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        DECLARE
          cursor_id uuid;
          parent_id uuid;
          step integer;
          command_setting text;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            command_setting := current_setting('coeus.organisation_reparent_command', true);
            IF command_setting IS NULL OR command_setting = '' OR NOT EXISTS (
              SELECT 1 FROM organisation_reparent_commands command_row
              WHERE command_row.command_id = command_setting::uuid
                AND command_row.occurred_at = transaction_timestamp()
                AND EXISTS (
                  SELECT 1 FROM organisation_unit_closure subtree
                  WHERE subtree.ancestor_unit_id = command_row.unit_id
                    AND subtree.descendant_unit_id = OLD.descendant_unit_id
                )
                AND NOT EXISTS (
                  SELECT 1 FROM organisation_unit_closure subtree
                  WHERE subtree.ancestor_unit_id = command_row.unit_id
                    AND subtree.descendant_unit_id = OLD.ancestor_unit_id
                )
            ) THEN
              RAISE EXCEPTION 'organisation closure rows are immutable';
            END IF;
            RETURN OLD;
          END IF;
          IF TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'organisation closure rows are immutable';
          END IF;
          cursor_id := NEW.descendant_unit_id;
          IF NEW.depth > 0 THEN
            FOR step IN 1..NEW.depth LOOP
              SELECT parent_unit_id INTO parent_id
              FROM organisation_units WHERE unit_id = cursor_id;
              IF parent_id IS NULL THEN
                RAISE EXCEPTION 'organisation closure depth exceeds the parent path';
              END IF;
              cursor_id := parent_id;
            END LOOP;
          END IF;
          IF cursor_id <> NEW.ancestor_unit_id THEN
            RAISE EXCEPTION 'organisation closure does not match the parent path';
          END IF;
          RETURN NEW;
        END
        $function$
        """,
    )
