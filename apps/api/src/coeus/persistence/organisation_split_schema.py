"""PostgreSQL schema for explicit-mapping organisation splits."""

from collections.abc import Sequence


def organisation_split_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS organisation_split_commands (
          command_id uuid PRIMARY KEY,
          idempotency_key text NOT NULL UNIQUE
            CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
          request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          reason_hash text NOT NULL CHECK (reason_hash ~ '^[0-9a-f]{64}$'),
          actor_user_id uuid NOT NULL,
          source_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          parent_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          source_expected_version bigint NOT NULL CHECK (source_expected_version > 0),
          parent_expected_version bigint NOT NULL CHECK (parent_expected_version > 0),
          source_result_version bigint NOT NULL CHECK (source_result_version > 0),
          parent_result_version bigint NOT NULL CHECK (parent_result_version > 0),
          successor_specs jsonb NOT NULL,
          source_authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id)
            ON DELETE RESTRICT,
          parent_authorising_grant_id uuid NOT NULL REFERENCES team_management_grants(grant_id)
            ON DELETE RESTRICT,
          occurred_at timestamptz NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS organisation_split_dispositions (
          command_id uuid NOT NULL REFERENCES organisation_split_commands(command_id)
            ON DELETE RESTRICT,
          record_kind text NOT NULL CHECK (record_kind IN
            ('child_unit','membership','grant','delivery_profile','capability','task',
             'pending_transfer')),
          record_id uuid NOT NULL,
          expected_version bigint NOT NULL CHECK (expected_version > 0),
          action text NOT NULL CHECK (action IN ('move','end','revoke','cancel')),
          target_unit_id uuid REFERENCES organisation_units(unit_id) ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED,
          replacement_id uuid,
          PRIMARY KEY (command_id,record_kind,record_id)
        )
        """,
        _split_topology_guard(),
    )


def _split_topology_guard() -> str:
    return """
    CREATE OR REPLACE FUNCTION validate_organisation_closure_write()
    RETURNS trigger LANGUAGE plpgsql AS $function$
    DECLARE
      cursor_id uuid;
      parent_id uuid;
      step integer;
      reparent_setting text;
      merge_setting text;
      split_setting text;
      allowed boolean := false;
    BEGIN
      IF TG_OP = 'DELETE' THEN
        reparent_setting := current_setting('coeus.organisation_reparent_command', true);
        IF reparent_setting IS NOT NULL AND reparent_setting <> '' THEN
          SELECT EXISTS (SELECT 1 FROM organisation_reparent_commands command_row
            WHERE command_row.command_id=reparent_setting::uuid
             AND command_row.occurred_at=transaction_timestamp()
             AND EXISTS (SELECT 1 FROM organisation_unit_closure subtree
              WHERE subtree.ancestor_unit_id=command_row.unit_id
               AND subtree.descendant_unit_id=OLD.descendant_unit_id)
             AND NOT EXISTS (SELECT 1 FROM organisation_unit_closure subtree
              WHERE subtree.ancestor_unit_id=command_row.unit_id
               AND subtree.descendant_unit_id=OLD.ancestor_unit_id)) INTO allowed;
        END IF;
        merge_setting := current_setting('coeus.organisation_merge_command', true);
        IF NOT allowed AND merge_setting IS NOT NULL AND merge_setting <> '' THEN
          SELECT EXISTS (SELECT 1 FROM organisation_merge_commands command_row
            JOIN organisation_merge_dispositions disposition
             ON disposition.command_id=command_row.command_id
            WHERE command_row.command_id=merge_setting::uuid
             AND command_row.occurred_at=transaction_timestamp()
             AND disposition.record_kind='child_unit' AND disposition.action='move'
             AND EXISTS (SELECT 1 FROM organisation_unit_closure subtree
              WHERE subtree.ancestor_unit_id=disposition.record_id
               AND subtree.descendant_unit_id=OLD.descendant_unit_id)
             AND NOT EXISTS (SELECT 1 FROM organisation_unit_closure subtree
              WHERE subtree.ancestor_unit_id=disposition.record_id
               AND subtree.descendant_unit_id=OLD.ancestor_unit_id)) INTO allowed;
        END IF;
        split_setting := current_setting('coeus.organisation_split_command', true);
        IF NOT allowed AND split_setting IS NOT NULL AND split_setting <> '' THEN
          SELECT EXISTS (SELECT 1 FROM organisation_split_commands command_row
            JOIN organisation_split_dispositions disposition
             ON disposition.command_id=command_row.command_id
            WHERE command_row.command_id=split_setting::uuid
             AND command_row.occurred_at=transaction_timestamp()
             AND disposition.record_kind='child_unit' AND disposition.action='move'
             AND EXISTS (SELECT 1 FROM organisation_unit_closure subtree
              WHERE subtree.ancestor_unit_id=disposition.record_id
               AND subtree.descendant_unit_id=OLD.descendant_unit_id)
             AND NOT EXISTS (SELECT 1 FROM organisation_unit_closure subtree
              WHERE subtree.ancestor_unit_id=disposition.record_id
               AND subtree.descendant_unit_id=OLD.ancestor_unit_id)) INTO allowed;
        END IF;
        IF NOT allowed THEN
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
          SELECT parent_unit_id INTO parent_id FROM organisation_units WHERE unit_id=cursor_id;
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
    """
