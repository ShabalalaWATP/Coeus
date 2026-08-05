"""Immutable profile and capability history required by restructure commands."""

from collections.abc import Sequence


def merge_history_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS team_delivery_profile_history (
          profile_id uuid NOT NULL,
          policy_version bigint NOT NULL CHECK (policy_version > 0),
          unit_id uuid NOT NULL,
          route text NOT NULL,
          wip_limit integer NOT NULL,
          weekly_hours numeric(6,2) NOT NULL,
          is_active boolean NOT NULL,
          provenance text NOT NULL,
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          recorded_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
          PRIMARY KEY (profile_id,policy_version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS team_capability_coverage_history (
          coverage_id uuid NOT NULL,
          policy_version bigint NOT NULL CHECK (policy_version > 0),
          profile_id uuid NOT NULL,
          capability_id text NOT NULL,
          proficiency smallint NOT NULL,
          valid_from timestamptz NOT NULL,
          valid_until timestamptz,
          approved_by_user_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          recorded_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
          PRIMARY KEY (coverage_id,policy_version)
        )
        """,
        """
        CREATE OR REPLACE FUNCTION preserve_team_delivery_profile_history()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        BEGIN
          INSERT INTO team_delivery_profile_history(profile_id,policy_version,unit_id,route,
            wip_limit,weekly_hours,is_active,provenance,created_at,updated_at)
          VALUES (OLD.profile_id,OLD.policy_version,OLD.unit_id,OLD.route,OLD.wip_limit,
            OLD.weekly_hours,OLD.is_active,OLD.provenance,OLD.created_at,OLD.updated_at)
          ON CONFLICT (profile_id,policy_version) DO NOTHING;
          RETURN NEW;
        END
        $function$
        """,
        """
        CREATE OR REPLACE FUNCTION preserve_team_capability_coverage_history()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        BEGIN
          INSERT INTO team_capability_coverage_history(coverage_id,policy_version,profile_id,
            capability_id,proficiency,valid_from,valid_until,approved_by_user_id,created_at)
          VALUES (OLD.coverage_id,OLD.policy_version,OLD.profile_id,OLD.capability_id,
            OLD.proficiency,OLD.valid_from,OLD.valid_until,OLD.approved_by_user_id,OLD.created_at)
          ON CONFLICT (coverage_id,policy_version) DO NOTHING;
          RETURN NEW;
        END
        $function$
        """,
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_trigger
            WHERE tgname='trg_team_delivery_profile_history'
              AND tgrelid='team_delivery_profiles'::regclass) THEN
            CREATE TRIGGER trg_team_delivery_profile_history
            BEFORE UPDATE ON team_delivery_profiles FOR EACH ROW
            EXECUTE FUNCTION preserve_team_delivery_profile_history();
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_trigger
            WHERE tgname='trg_team_capability_coverage_history'
              AND tgrelid='team_capability_coverage'::regclass) THEN
            CREATE TRIGGER trg_team_capability_coverage_history
            BEFORE UPDATE ON team_capability_coverage FOR EACH ROW
            EXECUTE FUNCTION preserve_team_capability_coverage_history();
          END IF;
        END
        $trigger$
        """,
        """
        CREATE OR REPLACE FUNCTION reject_organisation_history_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        BEGIN
          RAISE EXCEPTION 'organisation history is immutable';
        END
        $function$
        """,
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_trigger
            WHERE tgname='trg_team_delivery_profile_history_immutable'
              AND tgrelid='team_delivery_profile_history'::regclass) THEN
            CREATE TRIGGER trg_team_delivery_profile_history_immutable
            BEFORE UPDATE OR DELETE ON team_delivery_profile_history FOR EACH ROW
            EXECUTE FUNCTION reject_organisation_history_mutation();
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_trigger
            WHERE tgname='trg_team_capability_coverage_history_immutable'
              AND tgrelid='team_capability_coverage_history'::regclass) THEN
            CREATE TRIGGER trg_team_capability_coverage_history_immutable
            BEFORE UPDATE OR DELETE ON team_capability_coverage_history FOR EACH ROW
            EXECUTE FUNCTION reject_organisation_history_mutation();
          END IF;
        END
        $trigger$
        """,
    )
