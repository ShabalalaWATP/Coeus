from types import SimpleNamespace

import pytest

from coeus.persistence.draft_audience_reconciliation import AudienceReconciliationReport
from coeus.tools import reconcile_draft_audiences


def test_cli_defaults_to_read_only_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        reconcile_draft_audiences,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="secret-url"),
    )

    def reconcile(url: str, **kwargs: object) -> AudienceReconciliationReport:
        captured.update(url=url, **kwargs)
        return AudienceReconciliationReport(0, 0, (), ())

    monkeypatch.setattr(reconcile_draft_audiences, "reconcile_draft_audiences", reconcile)

    assert reconcile_draft_audiences.main(["--json"]) == 0
    assert captured["apply"] is False
    assert "secret-url" not in capsys.readouterr().out


def test_cli_requires_mutation_attribution() -> None:
    with pytest.raises(SystemExit, match="2"):
        reconcile_draft_audiences.main(["--apply"])


def test_cli_returns_drift_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        reconcile_draft_audiences,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="database"),
    )
    relationship = SimpleNamespace()
    monkeypatch.setattr(
        reconcile_draft_audiences,
        "reconcile_draft_audiences",
        lambda *_args, **_kwargs: AudienceReconciliationReport(1, 0, (relationship,), ()),
    )

    assert reconcile_draft_audiences.main([]) == 1
