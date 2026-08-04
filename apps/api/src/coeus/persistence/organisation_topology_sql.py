"""PostgreSQL triggers that make hierarchy closure a database invariant."""

from collections.abc import Sequence


def topology_integrity_statements() -> Sequence[str]:
    return (
        """
        CREATE OR REPLACE FUNCTION validate_organisation_unit_tree_integrity()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        DECLARE
          cursor_id uuid := NEW.unit_id;
          parent_id uuid;
          seen uuid[] := ARRAY[]::uuid[];
          expected_depth integer := 0;
          closure_count integer;
        BEGIN
          LOOP
            IF expected_depth > 12 THEN
              RAISE EXCEPTION 'organisation hierarchy exceeds maximum depth';
            END IF;
            IF cursor_id = ANY(seen) THEN
              RAISE EXCEPTION 'organisation hierarchy contains a cycle';
            END IF;
            seen := array_append(seen, cursor_id);
            SELECT parent_unit_id INTO parent_id
            FROM organisation_units WHERE unit_id = cursor_id;
            IF NOT FOUND THEN
              RAISE EXCEPTION 'organisation hierarchy references a missing unit';
            END IF;
            IF NOT EXISTS (
              SELECT 1 FROM organisation_unit_closure
              WHERE ancestor_unit_id = cursor_id
                AND descendant_unit_id = NEW.unit_id
                AND depth = expected_depth
            ) THEN
              RAISE EXCEPTION 'organisation closure is incomplete or inconsistent';
            END IF;
            expected_depth := expected_depth + 1;
            EXIT WHEN parent_id IS NULL;
            cursor_id := parent_id;
          END LOOP;
          SELECT count(*) INTO closure_count FROM organisation_unit_closure
          WHERE descendant_unit_id = NEW.unit_id;
          IF closure_count <> expected_depth THEN
            RAISE EXCEPTION 'organisation closure contains an invalid path';
          END IF;
          RETURN NEW;
        END
        $function$
        """,
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_organisation_unit_tree_integrity'
              AND tgrelid = 'organisation_units'::regclass
          ) THEN
            CREATE CONSTRAINT TRIGGER trg_organisation_unit_tree_integrity
            AFTER INSERT OR UPDATE OF parent_unit_id ON organisation_units
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION validate_organisation_unit_tree_integrity();
          END IF;
        END
        $trigger$
        """,
        """
        CREATE OR REPLACE FUNCTION validate_organisation_closure_write()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        DECLARE
          cursor_id uuid;
          parent_id uuid;
          step integer;
        BEGIN
          IF TG_OP <> 'INSERT' THEN
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
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_organisation_closure_write'
              AND tgrelid = 'organisation_unit_closure'::regclass
          ) THEN
            CREATE TRIGGER trg_organisation_closure_write
            BEFORE INSERT OR UPDATE OR DELETE ON organisation_unit_closure
            FOR EACH ROW EXECUTE FUNCTION validate_organisation_closure_write();
          END IF;
        END
        $trigger$
        """,
        """
        CREATE OR REPLACE FUNCTION validate_organisation_topology_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        DECLARE
          expected_path uuid[];
          expected_parent uuid;
        BEGIN
          IF cardinality(NEW.path) <> (
            SELECT count(DISTINCT item) FROM unnest(NEW.path) AS item
          ) THEN
            RAISE EXCEPTION 'organisation topology path contains a cycle';
          END IF;
          SELECT parent_unit_id INTO expected_parent
          FROM organisation_units WHERE unit_id = NEW.unit_id;
          SELECT array_agg(ancestor_unit_id ORDER BY depth DESC) INTO expected_path
          FROM organisation_unit_closure WHERE descendant_unit_id = NEW.unit_id;
          IF NEW.parent_unit_id IS DISTINCT FROM expected_parent OR NEW.path <> expected_path THEN
            RAISE EXCEPTION 'organisation topology revision does not match current topology';
          END IF;
          RETURN NEW;
        END
        $function$
        """,
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_organisation_topology_revision_validate'
              AND tgrelid = 'organisation_topology_revisions'::regclass
          ) THEN
            CREATE TRIGGER trg_organisation_topology_revision_validate
            BEFORE INSERT ON organisation_topology_revisions
            FOR EACH ROW EXECUTE FUNCTION validate_organisation_topology_revision_insert();
          END IF;
        END
        $trigger$
        """,
    )
