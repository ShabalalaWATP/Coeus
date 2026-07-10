from types import SimpleNamespace

import pytest

from coeus.tools import backfill_embeddings


def test_backfill_embeddings_cli_reports_updated_count(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Repository:
        def backfill_missing_embeddings(self) -> int:
            return 7

    app = SimpleNamespace(
        state=SimpleNamespace(
            store_services=SimpleNamespace(repository=Repository()),
        ),
    )
    monkeypatch.setattr(backfill_embeddings, "create_app", lambda _settings: app)

    backfill_embeddings.main()

    assert capsys.readouterr().out == "Backfilled 7 product embedding(s).\n"
