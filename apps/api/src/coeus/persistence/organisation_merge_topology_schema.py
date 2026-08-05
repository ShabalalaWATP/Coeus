"""Closure-write guard extended for explicit child dispositions in merges."""


def merge_topology_guard_statement() -> str:
    return """
    CREATE OR REPLACE FUNCTION validate_organisation_closure_write()
    RETURNS trigger LANGUAGE plpgsql AS $function$
    DECLARE
      cursor_id uuid;
      parent_id uuid;
      step integer;
      reparent_setting text;
      merge_setting text;
      reparent_allowed boolean := false;
      merge_allowed boolean := false;
    BEGIN
      IF TG_OP = 'DELETE' THEN
        reparent_setting := current_setting('coeus.organisation_reparent_command', true);
        IF reparent_setting IS NOT NULL AND reparent_setting <> '' THEN
          SELECT EXISTS (
            SELECT 1 FROM organisation_reparent_commands command_row
            WHERE command_row.command_id = reparent_setting::uuid
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
          ) INTO reparent_allowed;
        END IF;
        merge_setting := current_setting('coeus.organisation_merge_command', true);
        IF merge_setting IS NOT NULL AND merge_setting <> '' THEN
          SELECT EXISTS (
            SELECT 1 FROM organisation_merge_commands command_row
            JOIN organisation_merge_dispositions disposition
              ON disposition.command_id=command_row.command_id
            WHERE command_row.command_id = merge_setting::uuid
              AND command_row.occurred_at = transaction_timestamp()
              AND disposition.record_kind='child_unit'
              AND disposition.action='move'
              AND EXISTS (
                SELECT 1 FROM organisation_unit_closure subtree
                WHERE subtree.ancestor_unit_id = disposition.record_id
                  AND subtree.descendant_unit_id = OLD.descendant_unit_id
              )
              AND NOT EXISTS (
                SELECT 1 FROM organisation_unit_closure subtree
                WHERE subtree.ancestor_unit_id = disposition.record_id
                  AND subtree.descendant_unit_id = OLD.ancestor_unit_id
              )
          ) INTO merge_allowed;
        END IF;
        IF NOT reparent_allowed AND NOT merge_allowed THEN
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
    """
