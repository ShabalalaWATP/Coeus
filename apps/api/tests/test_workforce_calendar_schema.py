"""Static contract tests for the canonical workforce calendar schema."""

from importlib import import_module

from coeus.persistence.workforce_calendar_schema import workforce_calendar_schema_statements


def test_calendar_schema_has_canonical_privacy_version_and_command_boundaries() -> None:
    ddl = "\n".join(workforce_calendar_schema_statements())
    assert "CREATE TABLE calendar_events" in ddl
    assert "CREATE TABLE calendar_event_scopes" in ddl
    assert "CREATE TABLE calendar_event_exceptions" in ddl
    assert "CREATE TABLE calendar_event_versions" in ddl
    assert "CREATE TABLE calendar_event_commands" in ddl
    assert "privacy_level IN ('private','team_summary','team_detail')" in ddl
    assert "availability_effect IN ('available','partial','unavailable')" in ddl
    assert "UNIQUE(actor_user_id, idempotency_key)" in ddl
    assert "calendar events are cancelled, not deleted" in ddl
    assert "calendar history is immutable" in ddl


def test_calendar_migration_advances_from_split_revision() -> None:
    migration = import_module("coeus.db.migrations.versions.20260803_0028_workforce_calendar")
    assert migration.revision == "20260803_0028"
    assert migration.down_revision == "20260803_0027"
    occurrence = import_module(
        "coeus.db.migrations.versions.20260804_0038_calendar_occurrence_actions"
    )
    assert occurrence.revision == "20260804_0038"
    assert occurrence.down_revision == "20260804_0037"
