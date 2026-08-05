"""Race, replay and collision guards for calendar-import persistence."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from coeus.domain.calendar_import import (
    CalendarImportCommand,
    CalendarImportConflict,
    CalendarImportFinding,
    CalendarImportInspection,
    CalendarImportResult,
)
from coeus.persistence.calendar_import_inspection import _finding_codes
from coeus.persistence.calendar_import_postgres import (
    PostgresCalendarImportStore,
    _replay,
    _request_hash,
)


class _Rows:
    def __init__(self, rows=(), scalar=None):  # type: ignore[no-untyped-def]
        self.rows = rows
        self.scalar = scalar

    def mappings(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)

    def scalar_one(self):  # type: ignore[no-untyped-def]
        return self.scalar


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *args):  # type: ignore[no-untyped-def]
        return False


class _Connection(_Context):
    def __init__(self, rows=(), occurred_at=None):  # type: ignore[no-untyped-def]
        self.rows = rows
        self.occurred_at = occurred_at

    def execution_options(self, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["isolation_level"] == "SERIALIZABLE"
        return self

    def begin(self):
        return _Context()

    def execute(self, statement, params=None):  # type: ignore[no-untyped-def]
        del params
        return (
            _Rows((), self.occurred_at)
            if "transaction_timestamp" in str(statement)
            else _Rows(self.rows)
        )


class _Engine:
    def __init__(self, connection):  # type: ignore[no-untyped-def]
        self.connection = connection

    def connect(self):
        return self.connection


def _command() -> CalendarImportCommand:
    return CalendarImportCommand(uuid4(), "import", uuid4(), "a" * 64)


def _row(command: CalendarImportCommand) -> dict[str, object]:
    return {
        "command_id": command.command_id,
        "actor_user_id": command.actor_user_id,
        "idempotency_key": command.idempotency_key,
        "request_hash": _request_hash(command),
        "preview_hash": command.preview_hash,
        "imported_count": 2,
        "existing_count": 1,
    }


def test_replay_rejects_ambiguous_and_changed_command_identity() -> None:
    command = _command()
    assert _replay(_Connection(), command) is None
    with pytest.raises(CalendarImportConflict, match="identity"):
        _replay(_Connection((_row(command), _row(command))), command)
    changed = _row(command)
    changed["preview_hash"] = "b" * 64
    with pytest.raises(CalendarImportConflict, match="identity"):
        _replay(_Connection((changed,)), command)
    result = _replay(_Connection((_row(command),)), command)
    assert result == CalendarImportResult(command.command_id, 2, 1, True)


def test_collision_codes_are_complete_but_exact_replay_suppresses_identity_codes() -> None:
    missing = {
        "owner_active": False,
        "creator_present": False,
        "team_active": False,
        "owner_member": False,
        "identity_collision": True,
        "event_present": True,
        "record_present": True,
        "exact_replay": False,
    }
    assert _finding_codes(missing) == (
        "owner_account_missing",
        "creator_account_missing",
        "team_scope_missing",
        "owner_not_team_member",
        "canonical_identity_collision",
        "canonical_event_collision",
        "legacy_provenance_collision",
    )
    exact = {key: True for key in missing}
    assert _finding_codes(exact) == ()


@pytest.mark.parametrize("failure", ("stale", "findings", "clock"))
def test_serialisable_apply_rechecks_preview_and_transaction_time(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    command = _command()
    connection = _Connection(occurred_at=None if failure == "clock" else datetime.now(UTC))
    store = PostgresCalendarImportStore(_Engine(connection))  # type: ignore[arg-type]
    monkeypatch.setattr("coeus.persistence.calendar_import_postgres._replay", lambda *args: None)
    state = "b" * 64
    findings = (
        (CalendarImportFinding("canonical_event_collision", uuid4()),)
        if failure == "findings"
        else ()
    )
    monkeypatch.setattr(
        "coeus.persistence.calendar_import_postgres.inspect_calendar_import",
        lambda *args: CalendarImportInspection(state, (), 0, findings),
    )
    if failure != "stale":
        from coeus.domain.calendar_import import calendar_import_preview_hash

        command = SimpleNamespace(
            **{
                **vars(command),
                "preview_hash": calendar_import_preview_hash(
                    command.actor_user_id, "c" * 64, state
                ),
            }
        )
    expected = "stale" if failure == "stale" else "blocking" if failure == "findings" else "time"
    with pytest.raises((CalendarImportConflict, RuntimeError), match=expected):
        store.apply(command, "c" * 64, ())  # type: ignore[arg-type]


def test_serialisable_apply_returns_an_in_transaction_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = _command()
    expected = CalendarImportResult(command.command_id, 3, 1, True)
    monkeypatch.setattr(
        "coeus.persistence.calendar_import_postgres._replay", lambda *args: expected
    )
    store = PostgresCalendarImportStore(_Engine(_Connection()))  # type: ignore[arg-type]
    assert store.apply(command, "c" * 64, ()) is expected
