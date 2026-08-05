"""PostgreSQL schema for saved views, templates and work updates."""

from collections.abc import Sequence


def workspace_productivity_schema_statements() -> Sequence[str]:
    return (
        _VIEWS,
        _TEMPLATES,
        _UPDATES,
        _PREFERENCES,
        _STORE_LINKS,
        _COMMANDS,
        _INDEXES,
        _IMMUTABLE_FUNCTION,
        _IMMUTABLE_TRIGGER,
    )


_VIEWS = """
CREATE TABLE IF NOT EXISTS workspace_saved_views (
  view_id uuid PRIMARY KEY,
  owner_user_id uuid NOT NULL,
  unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
  filters jsonb NOT NULL CHECK (jsonb_typeof(filters)='object'),
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  UNIQUE(owner_user_id,name)
)
"""

_TEMPLATES = """
CREATE TABLE IF NOT EXISTS team_work_templates (
  template_id uuid PRIMARY KEY,
  unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  owner_user_id uuid NOT NULL,
  name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
  package_titles jsonb NOT NULL CHECK (jsonb_typeof(package_titles)='array'),
  estimated_minutes integer CHECK (estimated_minutes BETWEEN 15 AND 10080),
  priority smallint CHECK (priority BETWEEN 1 AND 5),
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  UNIQUE(unit_id,name)
)
"""

_UPDATES = """
CREATE TABLE IF NOT EXISTS workspace_work_updates (
  update_id uuid PRIMARY KEY,
  recipient_user_id uuid NOT NULL,
  event_key text NOT NULL CHECK (char_length(event_key) BETWEEN 1 AND 128),
  kind text NOT NULL CHECK (kind IN (
    'assignment','mention','due_soon','blocked_review','returned',
    'transfer_request','calendar_conflict','delegation_expiry'
  )),
  unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  object_type text NOT NULL CHECK (object_type IN ('ticket','work_package','calendar','grant')),
  object_id uuid NOT NULL,
  occurred_at timestamptz NOT NULL,
  acknowledged_at timestamptz,
  UNIQUE(recipient_user_id,event_key)
)
"""

_PREFERENCES = """
CREATE TABLE IF NOT EXISTS workspace_delivery_preferences (
  user_id uuid PRIMARY KEY,
  mode text NOT NULL CHECK (mode IN ('immediate','digest')),
  due_reminders boolean NOT NULL,
  version bigint NOT NULL CHECK (version > 0),
  updated_at timestamptz NOT NULL
)
"""

_STORE_LINKS = """
CREATE TABLE IF NOT EXISTS workspace_store_links (
  link_id uuid PRIMARY KEY,
  owner_user_id uuid NOT NULL,
  unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  source_type text NOT NULL CHECK (source_type IN ('ticket','work_package')),
  source_id uuid NOT NULL,
  target_type text NOT NULL CHECK (target_type IN ('project','product')),
  target_id uuid NOT NULL,
  label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 160),
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  UNIQUE(source_type,source_id,target_type,target_id)
)
"""

_COMMANDS = """
CREATE TABLE IF NOT EXISTS workspace_productivity_commands (
  command_id uuid PRIMARY KEY,
  actor_user_id uuid NOT NULL,
  idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
  request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  operation text NOT NULL CHECK (char_length(operation) BETWEEN 1 AND 50),
  result jsonb NOT NULL CHECK (jsonb_typeof(result)='object'),
  occurred_at timestamptz NOT NULL,
  UNIQUE(actor_user_id,idempotency_key)
)
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_workspace_views_owner_page
ON workspace_saved_views(owner_user_id,view_id);
CREATE INDEX IF NOT EXISTS idx_workspace_templates_unit_page
ON team_work_templates(unit_id,template_id);
CREATE INDEX IF NOT EXISTS idx_workspace_updates_recipient_page
ON workspace_work_updates(recipient_user_id,update_id);
CREATE INDEX IF NOT EXISTS idx_workspace_store_links_source_page
ON workspace_store_links(unit_id,source_type,source_id,link_id)
"""

_IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION reject_workspace_productivity_command_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'workspace productivity commands are immutable'; END
$$
"""

_IMMUTABLE_TRIGGER = """
DROP TRIGGER IF EXISTS trg_workspace_productivity_commands_immutable
ON workspace_productivity_commands;
CREATE TRIGGER trg_workspace_productivity_commands_immutable
BEFORE UPDATE OR DELETE ON workspace_productivity_commands
FOR EACH ROW EXECUTE FUNCTION reject_workspace_productivity_command_mutation()
"""
