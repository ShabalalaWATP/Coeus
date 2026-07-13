from types import SimpleNamespace

import pytest

from coeus.persistence.ticket_forward_reconciliation import ForwardReconciliationReport
from coeus.tools import reconcile_legacy_tickets


def test_cli_requires_quiescence_and_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit, match="2"):
        reconcile_legacy_tickets.main(["--operator", "ops", "--reason", "test"])

    monkeypatch.setattr(
        reconcile_legacy_tickets,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="memory", database_url="unused"),
    )
    with pytest.raises(SystemExit, match="2"):
        reconcile_legacy_tickets.main(
            ["--confirm-quiesced", "--operator", "ops", "--reason", "test"]
        )


def test_cli_reports_success_without_disclosing_database_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        reconcile_legacy_tickets,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="secret-url"),
    )
    monkeypatch.setattr(
        reconcile_legacy_tickets,
        "reconcile_legacy_ticket_state",
        lambda *_args, **_kwargs: ForwardReconciliationReport(2, 1, 0, "checkpoint-1"),
    )

    assert (
        reconcile_legacy_tickets.main(
            ["--confirm-quiesced", "--operator", "ops", "--reason", "test"]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert '"changed_count": 1' in output
    assert "secret-url" not in output


def test_cli_returns_failure_without_disclosing_database_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        reconcile_legacy_tickets,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="secret-url"),
    )
    monkeypatch.setattr(
        reconcile_legacy_tickets,
        "reconcile_legacy_ticket_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unsafe state")),
    )

    assert (
        reconcile_legacy_tickets.main(
            ["--confirm-quiesced", "--operator", "ops", "--reason", "test"]
        )
        == 1
    )
    output = capsys.readouterr().err
    assert "unsafe state" in output
    assert "secret-url" not in output
