"""Serializable PostgreSQL adapter for the synthetic organisation fixture."""

import json
from dataclasses import asdict, replace
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixtureConflict,
    SyntheticFixtureCounts,
    SyntheticFixtureIdempotencyConflict,
    SyntheticFixturePreview,
    SyntheticFixtureResult,
    SyntheticFixtureUser,
)
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.synthetic_fixture_inspection import inspect_fixture
from coeus.persistence.synthetic_fixture_reconcile import (
    can_reconcile,
    reconcile_exact_fixture_rows,
)
from coeus.persistence.synthetic_fixture_values import MANIFEST_VERSION
from coeus.persistence.synthetic_fixture_writes import (
    append_fixture_evidence,
    apply_fixture_plan,
)
from coeus.repositories.synthetic_organisation_manifest import synthetic_unit_specs


class PostgresSyntheticOrganisationFixtureStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def preview(
        self,
        actor_user_id: UUID,
        users: tuple[SyntheticFixtureUser, ...],
    ) -> SyntheticFixturePreview:
        with self._engine.begin() as connection:
            return inspect_fixture(connection, actor_user_id, users).preview

    def apply(
        self,
        command: SyntheticFixtureCommand,
        users: tuple[SyntheticFixtureUser, ...],
    ) -> SyntheticFixtureResult:
        return retry_serializable_once(lambda: self._apply_once(command, users, reconcile=False))

    def reconcile(
        self,
        command: SyntheticFixtureCommand,
        users: tuple[SyntheticFixtureUser, ...],
    ) -> SyntheticFixtureResult:
        return retry_serializable_once(lambda: self._apply_once(command, users, reconcile=True))

    def _apply_once(
        self,
        command: SyntheticFixtureCommand,
        users: tuple[SyntheticFixtureUser, ...],
        *,
        reconcile: bool,
    ) -> SyntheticFixtureResult:
        with self._engine.begin() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "coeus:synthetic-organisation-fixture:v2"},
            )
            mode = "reconcile" if reconcile else "apply"
            replay = _replay(_load_command(connection, command), command, mode)
            if replay is not None:
                return replay
            plan = inspect_fixture(connection, command.actor_user_id, users)
            if command.preview_hash != plan.preview.preview_hash:
                raise SyntheticFixtureConflict(
                    "fixture state changed after preview; review a fresh preview"
                )
            reconciled_rows = 0
            if reconcile and can_reconcile(plan.preview.findings):
                reconciled_rows = len(plan.preview.findings)
                reconcile_exact_fixture_rows(
                    connection,
                    {item.username.casefold(): item for item in users},
                )
                plan = inspect_fixture(connection, command.actor_user_id, users)
            if plan.preview.findings:
                raise SyntheticFixtureConflict(
                    "fixture preview contains conflicts that must be resolved"
                )
            occurred_at = _transaction_time(connection)
            apply_fixture_plan(
                connection,
                plan,
                command.actor_user_id,
                users,
                occurred_at,
            )
            result = SyntheticFixtureResult(
                command.command_id,
                MANIFEST_VERSION,
                plan.preview.creates,
                reconciled_rows=reconciled_rows,
            )
            payload: dict[str, object] = {
                "command_id": str(command.command_id),
                "manifest_version": MANIFEST_VERSION,
                "created": asdict(result.created),
                "mode": mode,
                "reconciled_rows": reconciled_rows,
            }
            _write_command(connection, command, payload, occurred_at)
            append_fixture_evidence(
                connection,
                command.command_id,
                command.actor_user_id,
                synthetic_unit_specs()[0].unit_id,
                occurred_at,
                payload,
            )
            return result


def _load_command(
    connection: Connection,
    command: SyntheticFixtureCommand,
) -> tuple[RowMapping, ...]:
    return tuple(
        connection.execute(
            text(
                "SELECT * FROM synthetic_organisation_fixture_commands "
                "WHERE command_id=:command_id OR idempotency_key=:idempotency_key "
                "ORDER BY command_id"
            ),
            {
                "command_id": command.command_id,
                "idempotency_key": command.idempotency_key,
            },
        ).mappings()
    )


def _replay(
    rows: tuple[RowMapping, ...],
    command: SyntheticFixtureCommand,
    mode: str,
) -> SyntheticFixtureResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise SyntheticFixtureIdempotencyConflict(
            "command and idempotency key identify different fixture operations"
        )
    row = rows[0]
    if not (
        UUID(str(row["command_id"])) == command.command_id
        and str(row["idempotency_key"]) == command.idempotency_key
        and str(row["request_hash"]) == command.preview_hash
        and UUID(str(row["actor_user_id"])) == command.actor_user_id
        and str(row["manifest_version"]) == MANIFEST_VERSION
    ):
        raise SyntheticFixtureIdempotencyConflict(
            "command or idempotency key is already used by another fixture operation"
        )
    payload = row["result"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    if payload.get("mode", "apply") != mode:
        raise SyntheticFixtureIdempotencyConflict(
            "command or idempotency key is already used by another fixture operation"
        )
    result = SyntheticFixtureResult(
        command.command_id,
        str(payload["manifest_version"]),
        SyntheticFixtureCounts(**payload["created"]),
        reconciled_rows=int(payload.get("reconciled_rows", 0)),
    )
    return replace(result, replayed=True)


def _write_command(
    connection: Connection,
    command: SyntheticFixtureCommand,
    payload: dict[str, object],
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(
            "INSERT INTO synthetic_organisation_fixture_commands"
            "(command_id,idempotency_key,request_hash,actor_user_id,manifest_version,"
            "result,occurred_at) VALUES (:command_id,:idempotency_key,:request_hash,"
            ":actor_id,:manifest_version,CAST(:result AS jsonb),:occurred_at)"
        ),
        {
            "command_id": command.command_id,
            "idempotency_key": command.idempotency_key,
            "request_hash": command.preview_hash,
            "actor_id": command.actor_user_id,
            "manifest_version": MANIFEST_VERSION,
            "result": json.dumps(payload, sort_keys=True),
            "occurred_at": occurred_at,
        },
    )


def _transaction_time(connection: Connection) -> datetime:
    value = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
    if not isinstance(value, datetime):
        raise RuntimeError("PostgreSQL did not return a transaction timestamp")
    return value
