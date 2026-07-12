from importlib import import_module
from typing import Any

import pytest


class RecordingOperations:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)


def test_append_only_audit_upgrade_uses_idempotent_legacy_compatible_ddl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = import_module("coeus.db.migrations.versions.20260710_0006_append_only_audit")
    operations = RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()
    migration.upgrade()

    assert len(operations.statements) == 4
    assert all("IF NOT EXISTS" in statement for statement in operations.statements)
    assert "CREATE TABLE IF NOT EXISTS coeus_audit_events" in operations.statements[0]
    assert "CREATE INDEX IF NOT EXISTS idx_coeus_audit_events_order" in operations.statements[1]


def test_append_only_audit_downgrade_remains_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = import_module("coeus.db.migrations.versions.20260710_0006_append_only_audit")
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    class DowngradeOperations:
        def drop_index(self, name: str, *args: Any, **kwargs: Any) -> None:
            calls.append((name, args, kwargs))

        def drop_table(self, name: str, *args: Any, **kwargs: Any) -> None:
            calls.append((name, args, kwargs))

    monkeypatch.setattr(migration, "op", DowngradeOperations())

    migration.downgrade()

    assert calls == [
        ("idx_coeus_audit_events_order", (), {"table_name": "coeus_audit_events"}),
        ("coeus_audit_events", (), {}),
    ]
