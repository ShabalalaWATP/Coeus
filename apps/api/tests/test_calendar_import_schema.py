"""Static migration and schema contracts for legacy-calendar import."""

from importlib import import_module

from coeus.persistence.calendar_import_schema import calendar_import_schema_statements


def test_calendar_import_schema_is_append_only_and_preview_bound() -> None:
    ddl = "\n".join(calendar_import_schema_statements())
    assert "CREATE TABLE calendar_import_commands" in ddl
    assert "CREATE TABLE calendar_legacy_import_records" in ddl
    assert "preview_hash char(64)" in ddl
    assert "UNIQUE(actor_user_id,idempotency_key)" in ddl
    assert "calendar import evidence is immutable" in ddl
    assert "legacy_entry_id uuid PRIMARY KEY" in ddl


def test_calendar_import_migration_follows_dependency_commands() -> None:
    migration = import_module("coeus.db.migrations.versions.20260804_0035_calendar_import")
    assert migration.revision == "20260804_0035"
    assert migration.down_revision == "20260804_0034"
