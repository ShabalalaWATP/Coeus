"""Fail-closed branch coverage for synthetic fixture command replay."""

import json
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixtureCounts,
    SyntheticFixtureIdempotencyConflict,
)
from coeus.persistence.synthetic_fixture_values import MANIFEST_VERSION
from coeus.persistence.synthetic_organisation_fixture_postgres import (
    _replay,
    _transaction_time,
)

NOW = datetime(2026, 8, 4, 9, tzinfo=UTC)


def _command() -> SyntheticFixtureCommand:
    return SyntheticFixtureCommand(uuid4(), "fixture-branch-coverage", uuid4(), "a" * 64)


def _row(command: SyntheticFixtureCommand, *, string_payload: bool = False) -> RowMapping:
    payload: object = {
        "manifest_version": MANIFEST_VERSION,
        "created": vars(SyntheticFixtureCounts()),
        "mode": "apply",
        "reconciled_rows": 0,
    }
    if string_payload:
        payload = json.dumps(payload)
    return cast(
        RowMapping,
        {
            "command_id": command.command_id,
            "idempotency_key": command.idempotency_key,
            "request_hash": command.preview_hash,
            "actor_user_id": command.actor_user_id,
            "manifest_version": MANIFEST_VERSION,
            "result": payload,
        },
    )


def test_fixture_replay_handles_absence_identity_and_json_payloads() -> None:
    command = _command()
    assert _replay((), command, "apply") is None
    with pytest.raises(SyntheticFixtureIdempotencyConflict, match="different fixture"):
        _replay((_row(command), _row(command)), command, "apply")
    with pytest.raises(SyntheticFixtureIdempotencyConflict, match="another fixture"):
        _replay(
            (cast(RowMapping, {**dict(_row(command)), "request_hash": "b" * 64}),),
            command,
            "apply",
        )
    with pytest.raises(SyntheticFixtureIdempotencyConflict, match="another fixture"):
        _replay((_row(command),), command, "reconcile")
    replay = _replay((_row(command, string_payload=True),), command, "apply")
    assert replay is not None and replay.replayed


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one(self) -> object:
        return self.value


class _ScalarConnection:
    def __init__(self, value: object) -> None:
        self.value = value

    def execute(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self.value)


def test_fixture_transaction_time_requires_a_datetime() -> None:
    assert _transaction_time(cast(Connection, _ScalarConnection(NOW))) == NOW
    with pytest.raises(RuntimeError, match="transaction timestamp"):
        _transaction_time(cast(Connection, _ScalarConnection("invalid")))
