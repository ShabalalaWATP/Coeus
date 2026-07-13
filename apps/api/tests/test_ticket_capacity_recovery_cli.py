from types import SimpleNamespace
from uuid import uuid4

import pytest

from coeus.persistence.ticket_capacity_recovery import CapacityReport
from coeus.tools import ticket_capacity_recovery


def _report() -> CapacityReport:
    return CapacityReport(1, {}, (), (), ())


def test_cli_defaults_to_dry_run_and_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        ticket_capacity_recovery,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="secret-url"),
    )

    def recover(url: str, **kwargs: object) -> CapacityReport:
        captured.update(url=url, **kwargs)
        return _report()

    monkeypatch.setattr(ticket_capacity_recovery, "recover_ticket_capacity", recover)

    assert ticket_capacity_recovery.main(["--json"]) == 0
    assert captured["action"] == "inspect"
    assert "secret-url" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["--remove-expired"],
        ["--repair-projection", "--operator", "ops"],
        ["--release-lease", str(uuid4()), "--operator", "ops", "--reason", "stuck"],
    ],
)
def test_cli_refuses_unsafe_mutation_arguments(arguments: list[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        ticket_capacity_recovery.main(arguments)


def test_cli_reports_fail_closed_recovery_without_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        ticket_capacity_recovery,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="secret-url"),
    )
    monkeypatch.setattr(
        ticket_capacity_recovery,
        "recover_ticket_capacity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unsafe projection")),
    )

    assert ticket_capacity_recovery.main([]) == 1
    output = capsys.readouterr()
    assert "unsafe projection" in output.err
    assert "secret-url" not in output.err
