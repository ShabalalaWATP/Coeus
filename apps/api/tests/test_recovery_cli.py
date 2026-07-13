import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from coeus.services.coordinated_restore import RestoreDrillReport
from coeus.tools import coordinated_restore_drill, reverse_ticket_projection


def _settings(**overrides: object) -> SimpleNamespace:
    values = {
        "persistence_provider": "postgres",
        "object_storage_provider": "local",
        "database_url": "source-database",
        "local_object_storage_path": "source-objects",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_coordinated_restore_cli_runs_and_emits_machine_readable_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(coordinated_restore_drill, "Settings", _settings)
    monkeypatch.setenv("COEUS_RESTORE_TARGET_DATABASE_URL", "target-database")
    monkeypatch.setattr(
        coordinated_restore_drill,
        "create_backup_bundle",
        lambda *args, **kwargs: calls.append((*args, kwargs)),
    )
    monkeypatch.setattr(
        coordinated_restore_drill,
        "restore_backup_bundle",
        lambda *args, **kwargs: (
            calls.append((*args, kwargs)) or RestoreDrillReport("recovery-1", "head", 9, 2)
        ),
    )

    result = coordinated_restore_drill.main(
        [
            "--bundle",
            str(tmp_path / "bundle"),
            "--target-object-root",
            str(tmp_path / "restored"),
            "--confirm-quiesced",
        ]
    )

    assert result == 0
    assert len(calls) == 2
    assert json.loads(capsys.readouterr().out) == {
        "alembic_revision": "head",
        "object_count": 2,
        "recovery_id": "recovery-1",
        "table_count": 9,
    }


@pytest.mark.parametrize(
    ("arguments", "settings", "target"),
    [
        (["--bundle", "b", "--target-object-root", "o"], _settings(), "target"),
        (
            ["--bundle", "b", "--target-object-root", "o", "--confirm-quiesced"],
            _settings(persistence_provider="memory"),
            "target",
        ),
        (
            ["--bundle", "b", "--target-object-root", "o", "--confirm-quiesced"],
            _settings(),
            None,
        ),
    ],
)
def test_coordinated_restore_cli_rejects_unsafe_configuration(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    settings: SimpleNamespace,
    target: str | None,
) -> None:
    monkeypatch.setattr(coordinated_restore_drill, "Settings", lambda: settings)
    if target is None:
        monkeypatch.delenv("COEUS_RESTORE_TARGET_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("COEUS_RESTORE_TARGET_DATABASE_URL", target)

    with pytest.raises(SystemExit, match="2"):
        coordinated_restore_drill.main(arguments)


def test_coordinated_restore_cli_reports_safe_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr(coordinated_restore_drill, "Settings", _settings)
    monkeypatch.setenv("COEUS_RESTORE_TARGET_DATABASE_URL", "target-database")
    monkeypatch.setattr(
        coordinated_restore_drill,
        "create_backup_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic drift")),
    )

    result = coordinated_restore_drill.main(
        [
            "--bundle",
            str(tmp_path / "bundle"),
            "--target-object-root",
            str(tmp_path / "objects"),
            "--confirm-quiesced",
        ]
    )

    assert result == 1
    assert "synthetic drift" in capsys.readouterr().err


def test_reverse_projection_cli_requires_confirmation_and_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["reverse-ticket-projection"])
    with pytest.raises(SystemExit, match="2"):
        reverse_ticket_projection.main()

    monkeypatch.setattr(sys, "argv", ["reverse-ticket-projection", "--confirm-quiesced"])
    monkeypatch.setattr(
        reverse_ticket_projection,
        "Settings",
        lambda: _settings(persistence_provider="memory"),
    )
    with pytest.raises(SystemExit, match="2"):
        reverse_ticket_projection.main()


def test_reverse_projection_cli_initialises_schema_and_reports_count(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    loaded: list[str] = []

    class Store:
        def __init__(self, database_url: str, mode: str) -> None:
            loaded.extend((database_url, mode))

        def load_ticket_state(self) -> None:
            loaded.append("loaded")

    monkeypatch.setattr(sys, "argv", ["reverse-ticket-projection", "--confirm-quiesced"])
    monkeypatch.setattr(reverse_ticket_projection, "Settings", _settings)
    monkeypatch.setattr(reverse_ticket_projection, "PostgresStateStore", Store)
    monkeypatch.setattr(reverse_ticket_projection, "reverse_project_ticket_state", lambda _: 3)

    assert reverse_ticket_projection.main() == 0
    assert loaded == ["source-database", "relational", "loaded"]
    assert "Reverse-projected 3" in capsys.readouterr().out
