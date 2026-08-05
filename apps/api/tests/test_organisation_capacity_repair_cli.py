from types import SimpleNamespace
from uuid import uuid4

import pytest

from coeus.persistence.organisation_capacity_repair import OrganisationCapacityRepairReport
from coeus.tools import organisation_capacity_repair


def _report(*, issues: bool = False) -> OrganisationCapacityRepairReport:
    if not issues:
        return OrganisationCapacityRepairReport((), (), ())
    return OrganisationCapacityRepairReport((), (), (), truncated=True)


def test_cli_defaults_to_read_only_json(monkeypatch: pytest.MonkeyPatch, capsys) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        organisation_capacity_repair,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="secret-url"),
    )

    def inspect(url: str, **kwargs: object) -> OrganisationCapacityRepairReport:
        captured.update(url=url, **kwargs)
        return _report()

    monkeypatch.setattr(
        organisation_capacity_repair, "inspect_or_repair_organisation_capacity", inspect
    )

    assert organisation_capacity_repair.main(["--json"]) == 0
    assert captured["action"] == "inspect"
    assert "secret-url" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["--repair-reservations"],
        ["--repair-reservations", "--operator", str(uuid4()), "--reason", "reviewed"],
    ],
)
def test_cli_refuses_unreviewed_repairs(arguments: list[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        organisation_capacity_repair.main(arguments)


def test_cli_reports_refusal_and_remaining_issues(monkeypatch: pytest.MonkeyPatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        organisation_capacity_repair,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="hidden"),
    )
    monkeypatch.setattr(
        organisation_capacity_repair,
        "inspect_or_repair_organisation_capacity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("ambiguous authority")),
    )
    assert organisation_capacity_repair.main([]) == 1
    output = capsys.readouterr()
    assert "ambiguous authority" in output.err and "hidden" not in output.err

    monkeypatch.setattr(
        organisation_capacity_repair,
        "inspect_or_repair_organisation_capacity",
        lambda *_args, **_kwargs: _report(issues=True),
    )
    assert organisation_capacity_repair.main([]) == 1


def test_cli_repair_forwards_reviewed_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    operator = uuid4()
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        organisation_capacity_repair,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="postgres", database_url="hidden"),
    )

    def repair_call(_url: str, **kwargs: object) -> OrganisationCapacityRepairReport:
        captured.update(kwargs)
        return _report()

    monkeypatch.setattr(
        organisation_capacity_repair, "inspect_or_repair_organisation_capacity", repair_call
    )
    assert (
        organisation_capacity_repair.main(
            [
                "--repair-reservations",
                "--operator",
                str(operator),
                "--reason",
                "reviewed",
                "--confirm-reviewed",
            ]
        )
        == 0
    )
    assert captured == {
        "action": "repair-reservations",
        "operator_user_id": operator,
        "reason": "reviewed",
        "reviewed": True,
    }


def test_cli_requires_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        organisation_capacity_repair,
        "Settings",
        lambda: SimpleNamespace(persistence_provider="file", database_url="hidden"),
    )
    with pytest.raises(SystemExit, match="2"):
        organisation_capacity_repair.main([])
