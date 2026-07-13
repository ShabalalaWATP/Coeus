from pathlib import Path

import pytest

from coeus.persistence import postgres_logical_backup as backup
from coeus.persistence.backup_manifest import TableBackup


class Result:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class Connection:
    def __init__(self, rows: list[tuple[object, ...] | None]) -> None:
        self._rows = iter(rows)

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def transaction(self) -> "Connection":
        return self

    def execute(self, *_args: object, **_kwargs: object) -> Result:
        return Result(next(self._rows, (0,)))


def test_export_requires_an_alembic_revision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    connection = Connection([(0,), None])
    monkeypatch.setattr(backup.psycopg, "connect", lambda *_args, **_kwargs: connection)

    with pytest.raises(RuntimeError, match="no Alembic revision"):
        backup.export_tables("postgresql://localhost/source", tmp_path / "export")


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        (1, 1, "not empty"),
        (0, 2, "row count differs"),
    ],
)
def test_import_rejects_nonempty_or_mismatched_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    before: int,
    after: int,
    message: str,
) -> None:
    spec = backup.TableSpec("example", ("id",), ("id",))
    table = TableBackup("example", ("id",), 1, "tables/example.copy", "a" * 64)
    connection = Connection([(before,), (after,)])
    monkeypatch.setattr(backup, "TABLES", (spec,))
    monkeypatch.setattr(backup.psycopg, "connect", lambda *_args, **_kwargs: connection)
    monkeypatch.setattr(backup, "_require_table", lambda *_args: None)
    monkeypatch.setattr(backup, "_copy_in", lambda *_args: None)

    with pytest.raises(RuntimeError, match=message):
        backup.import_tables("postgresql://localhost/target", tmp_path, (table,))


def test_manifest_specs_must_match_the_release_allowlist() -> None:
    with pytest.raises(ValueError, match="allow-list"):
        backup._validate_specs(())

    tables = tuple(
        TableBackup(spec.name, spec.columns, 0, f"tables/{spec.name}.copy", "a" * 64)
        for spec in backup.TABLES
    )
    invalid = (TableBackup("unexpected", tables[0].columns, 0, tables[0].file, "a" * 64),)
    with pytest.raises(ValueError, match="schema differs"):
        backup._validate_specs((*invalid, *tables[1:]))


@pytest.mark.parametrize("row", [None, (None,)])
def test_required_table_check_fails_closed(row: tuple[object, ...] | None) -> None:
    connection = Connection([row])

    with pytest.raises(RuntimeError, match="does not exist"):
        backup._require_table(connection, "required_table")


def test_table_count_fails_closed_when_postgres_returns_no_row() -> None:
    connection = Connection([None])

    with pytest.raises(RuntimeError, match="export table example"):
        backup._table_count(connection, "example", operation="export")


def test_database_name_uses_parsed_url() -> None:
    assert backup.database_name("postgresql://user:password@localhost/example") == "example"
