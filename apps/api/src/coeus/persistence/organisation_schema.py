"""Idempotent PostgreSQL DDL for the inactive organisation bounded context."""

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from sqlalchemy import text

from coeus.domain.organisation import (
    DeliveryRoute,
    FindingSeverity,
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    ReconciliationStatus,
)
from coeus.persistence.organisation_topology_sql import topology_integrity_statements


def _values(items: type[StrEnum]) -> str:
    return ", ".join(f"'{item.value}'" for item in items)


def organisation_schema_statements() -> Sequence[str]:
    """Return the schema shared by runtime bootstrap and Alembic."""
    return (
        "CREATE EXTENSION IF NOT EXISTS btree_gist",
        f"""
        CREATE TABLE IF NOT EXISTS organisation_units (
          unit_id uuid PRIMARY KEY,
          name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
          short_name text NOT NULL CHECK (char_length(short_name) BETWEEN 1 AND 32),
          category text NOT NULL CHECK (category IN ({_values(OrganisationCategory)})),
          parent_unit_id uuid REFERENCES organisation_units(unit_id)
            DEFERRABLE INITIALLY IMMEDIATE,
          is_active boolean NOT NULL DEFAULT true,
          valid_from timestamptz NOT NULL,
          valid_until timestamptz,
          time_zone text NOT NULL CHECK (char_length(time_zone) BETWEEN 1 AND 64),
          description text NOT NULL DEFAULT '' CHECK (char_length(description) <= 1000),
          provenance text NOT NULL DEFAULT 'manual'
            CHECK (char_length(provenance) BETWEEN 1 AND 120),
          version bigint NOT NULL CHECK (version > 0),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_organisation_unit_not_self_parent
            CHECK (parent_unit_id IS NULL OR parent_unit_id <> unit_id),
          CONSTRAINT ck_organisation_unit_validity
            CHECK (valid_until IS NULL OR valid_until > valid_from)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organisation_units_parent
        ON organisation_units(parent_unit_id, unit_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS organisation_unit_closure (
          ancestor_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id)
            ON DELETE RESTRICT,
          descendant_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id)
            ON DELETE RESTRICT,
          depth smallint NOT NULL CHECK (depth BETWEEN 0 AND 12),
          PRIMARY KEY (ancestor_unit_id, descendant_unit_id),
          CONSTRAINT ck_organisation_closure_self_path CHECK (
            (depth = 0 AND ancestor_unit_id = descendant_unit_id) OR
            (depth > 0 AND ancestor_unit_id <> descendant_unit_id)
          )
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organisation_closure_descendant
        ON organisation_unit_closure(descendant_unit_id, depth, ancestor_unit_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS organisation_topology_revisions (
          revision_id uuid PRIMARY KEY,
          unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          parent_unit_id uuid REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          path uuid[] NOT NULL,
          valid_from timestamptz NOT NULL,
          valid_until timestamptz,
          change_command_id uuid NOT NULL,
          changed_by_user_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_organisation_topology_validity
            CHECK (valid_until IS NULL OR valid_until > valid_from),
          CONSTRAINT ck_organisation_topology_path CHECK (
            cardinality(path) BETWEEN 1 AND 13 AND
            path[cardinality(path)] = unit_id AND
            (parent_unit_id IS NULL OR
              (cardinality(path) > 1 AND path[cardinality(path) - 1] = parent_unit_id))
          ),
          UNIQUE (unit_id, valid_from)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_organisation_topology_unit
        ON organisation_topology_revisions(unit_id, valid_from DESC)
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_delivery_profiles (
          profile_id uuid PRIMARY KEY,
          unit_id uuid NOT NULL UNIQUE REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          route text NOT NULL CHECK (route IN ({_values(DeliveryRoute)})),
          wip_limit integer NOT NULL CHECK (wip_limit > 0),
          weekly_hours numeric(6,2) NOT NULL CHECK (weekly_hours > 0 AND weekly_hours <= 168),
          policy_version bigint NOT NULL CHECK (policy_version > 0),
          is_active boolean NOT NULL DEFAULT true,
          provenance text NOT NULL DEFAULT 'manual'
            CHECK (char_length(provenance) BETWEEN 1 AND 120),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS team_capability_coverage (
          coverage_id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES team_delivery_profiles(profile_id)
            ON DELETE RESTRICT,
          capability_id text NOT NULL CHECK (char_length(capability_id) BETWEEN 1 AND 120),
          proficiency smallint NOT NULL CHECK (proficiency BETWEEN 1 AND 5),
          valid_from timestamptz NOT NULL,
          valid_until timestamptz,
          policy_version bigint NOT NULL CHECK (policy_version > 0),
          approved_by_user_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_team_capability_validity
            CHECK (valid_until IS NULL OR valid_until > valid_from),
          UNIQUE (profile_id, capability_id, valid_from)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_memberships (
          membership_id uuid PRIMARY KEY,
          user_id uuid NOT NULL,
          unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          role text NOT NULL CHECK (role IN ({_values(MembershipRole)})),
          state text NOT NULL CHECK (state IN ({_values(MembershipState)})),
          assignment_eligible boolean NOT NULL DEFAULT false,
          valid_from timestamptz NOT NULL,
          valid_until timestamptz,
          created_by_user_id uuid NOT NULL,
          reason text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 500),
          provenance text NOT NULL CHECK (char_length(provenance) BETWEEN 1 AND 120),
          version bigint NOT NULL CHECK (version > 0),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_team_membership_validity
            CHECK (valid_until IS NULL OR valid_until > valid_from),
          CONSTRAINT ck_team_membership_ended CHECK (
            state <> 'ended' OR valid_until IS NOT NULL
          ),
          CONSTRAINT ck_team_membership_eligibility CHECK (
            NOT assignment_eligible OR state = 'active'
          ),
          CONSTRAINT ex_team_memberships_non_overlapping EXCLUDE USING gist (
            user_id WITH =,
            tstzrange(valid_from, valid_until, '[)') WITH &&
          ) WHERE (state <> 'cancelled')
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_team_memberships_unit
        ON team_memberships(unit_id, valid_from, user_id)
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_management_grants (
          grant_id uuid PRIMARY KEY,
          manager_user_id uuid NOT NULL,
          root_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          action text NOT NULL CHECK (action IN ({_values(ManagementAction)})),
          include_descendants boolean NOT NULL DEFAULT false,
          valid_from timestamptz NOT NULL,
          valid_until timestamptz,
          revoked_at timestamptz,
          created_by_user_id uuid NOT NULL,
          reason text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 500),
          source_grant_id uuid REFERENCES team_management_grants(grant_id) ON DELETE RESTRICT,
          delegation_depth smallint NOT NULL DEFAULT 0 CHECK (delegation_depth BETWEEN 0 AND 2),
          version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_team_grant_validity
            CHECK (
              (valid_until IS NULL OR valid_until > valid_from) AND
              (revoked_at IS NULL OR revoked_at >= valid_from) AND
              (revoked_at IS NULL OR valid_until IS NULL OR revoked_at <= valid_until)
            ),
          CONSTRAINT ck_team_grant_source CHECK (
            (source_grant_id IS NULL AND delegation_depth = 0) OR
            (source_grant_id IS NOT NULL AND delegation_depth > 0)
          ),
          CONSTRAINT ck_team_grant_not_self_source
            CHECK (source_grant_id IS NULL OR source_grant_id <> grant_id)
        )
        """,
        "ALTER TABLE team_management_grants ADD COLUMN IF NOT EXISTS version bigint "
        "NOT NULL DEFAULT 1 CHECK (version > 0)",
        """
        CREATE INDEX IF NOT EXISTS idx_team_management_grants_manager
        ON team_management_grants(manager_user_id, valid_from, valid_until)
        """,
        """
        CREATE TABLE IF NOT EXISTS effective_authority_epochs (
          principal_id uuid NOT NULL,
          scope_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          epoch bigint NOT NULL CHECK (epoch > 0),
          advanced_at timestamptz NOT NULL,
          PRIMARY KEY (principal_id, scope_unit_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS organisation_reconciliation_checkpoints (
          checkpoint_id uuid PRIMARY KEY,
          source_namespace text NOT NULL
            CHECK (char_length(source_namespace) BETWEEN 1 AND 120),
          source_digest text NOT NULL CHECK (char_length(source_digest) BETWEEN 1 AND 128),
          status text NOT NULL CHECK (status IN ({_values(ReconciliationStatus)})),
          cursor jsonb NOT NULL DEFAULT '{{}}'::jsonb,
          started_at timestamptz NOT NULL,
          completed_at timestamptz,
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_organisation_reconciliation_checkpoint_times CHECK (
            (status = 'running' AND completed_at IS NULL) OR
            (status <> 'running' AND completed_at IS NOT NULL AND completed_at >= started_at)
          ),
          UNIQUE (source_namespace, source_digest)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS organisation_reconciliation_findings (
          finding_id uuid PRIMARY KEY,
          checkpoint_id uuid NOT NULL REFERENCES organisation_reconciliation_checkpoints(
            checkpoint_id
          ) ON DELETE CASCADE,
          finding_code text NOT NULL CHECK (char_length(finding_code) BETWEEN 1 AND 120),
          severity text NOT NULL CHECK (severity IN ({_values(FindingSeverity)})),
          source_identifier text NOT NULL
            CHECK (char_length(source_identifier) BETWEEN 1 AND 240),
          details jsonb NOT NULL DEFAULT '{{}}'::jsonb,
          created_at timestamptz NOT NULL,
          resolved_at timestamptz,
          disposition text NOT NULL DEFAULT '' CHECK (char_length(disposition) <= 500),
          CONSTRAINT ck_organisation_reconciliation_finding_times
            CHECK (resolved_at IS NULL OR resolved_at >= created_at),
          UNIQUE (checkpoint_id, finding_code, source_identifier)
        )
        """,
        *topology_integrity_statements(),
        """
        CREATE OR REPLACE FUNCTION reject_organisation_topology_revision_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        BEGIN
          RAISE EXCEPTION 'organisation topology revisions are immutable';
        END
        $function$
        """,
        """
        DO $trigger$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_organisation_topology_revisions_immutable'
              AND tgrelid = 'organisation_topology_revisions'::regclass
          ) THEN
            CREATE TRIGGER trg_organisation_topology_revisions_immutable
            BEFORE UPDATE OR DELETE ON organisation_topology_revisions
            FOR EACH ROW EXECUTE FUNCTION reject_organisation_topology_revision_mutation();
          END IF;
        END
        $trigger$
        """,
    )


def ensure_organisation_schema(connection: Any) -> None:
    for statement in organisation_schema_statements():
        connection.execute(text(statement))
