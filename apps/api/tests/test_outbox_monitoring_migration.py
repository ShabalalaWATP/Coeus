from importlib import import_module

import pytest


class Operations:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)


def test_outbox_monitoring_migration_adds_and_removes_a_partial_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = import_module(
        "coeus.db.migrations.versions.20260720_0014_outbox_monitoring_indexes"
    )
    operations = Operations()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()
    migration.downgrade()

    assert migration.down_revision == "20260717_0013"
    assert operations.statements[0] == (
        "CREATE INDEX IF NOT EXISTS idx_coeus_outbox_dead_letters "
        "ON coeus_outbox(dead_lettered_at, event_id) "
        "WHERE delivered_at IS NULL AND dead_lettered_at IS NOT NULL"
    )
    assert operations.statements[1] == "DROP INDEX IF EXISTS idx_coeus_outbox_dead_letters"
