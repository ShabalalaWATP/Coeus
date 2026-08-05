"""Serialisable policy and export commands for team workspaces."""

import json
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.workspace_operations import (
    WorkspaceCommand,
    WorkspaceExport,
    WorkspaceOperationsConflict,
    WorkspaceOperationsDenied,
    WorkspacePolicy,
    WorkspaceScope,
)
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.workspace_operations_authority import resolve_workspace_authority
from coeus.persistence.workspace_operations_queries import _policy_row, analytics
from coeus.persistence.workspace_operations_sql import INSERT_COMMAND, INSERT_EXPORT, UPSERT_POLICY


class WorkspaceOperationsWriter:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save_policy(self, command: WorkspaceCommand) -> WorkspacePolicy:
        return retry_serializable_once(lambda: self._save_policy(command))

    def create_export(self, command: WorkspaceCommand) -> WorkspaceExport:
        return retry_serializable_once(lambda: self._create_export(command))

    def _save_policy(self, command: WorkspaceCommand) -> WorkspacePolicy:
        with (
            self._engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection,
            connection.begin(),
        ):
            at = transaction_time(connection)
            unit_id = UUID(str(command.payload["unit_id"]))
            grant = resolve_workspace_authority(
                connection,
                command.actor_user_id,
                unit_id,
                ManagementAction.WORKSPACE_CONFIGURE,
                WorkspaceScope.DIRECT,
                at,
                lock=True,
            )
            _match_grant(command, grant.grant_id, grant.grant_version)
            replay = _command_replay(connection, command)
            if replay is not None:
                return _load_policy(connection, unit_id)
            profile = (
                connection.execute(
                    text(
                        "SELECT policy_version FROM team_delivery_profiles WHERE unit_id=:unit "
                        "AND is_active FOR UPDATE"
                    ),
                    {"unit": unit_id},
                )
                .mappings()
                .first()
            )
            current = (
                connection.execute(
                    text(
                        "SELECT version FROM team_workspace_policies WHERE unit_id=:unit FOR UPDATE"
                    ),
                    {"unit": unit_id},
                )
                .mappings()
                .first()
            )
            expected = int(str(command.payload["expected_version"]))
            if (0 if current is None else int(current["version"])) != expected:
                raise WorkspaceOperationsConflict("workspace policy version changed")
            expected_delivery = int(str(command.payload["expected_delivery_policy_version"]))
            if profile is None or int(profile["policy_version"]) != expected_delivery:
                raise WorkspaceOperationsConflict("delivery policy version changed")
            values = _policy_values(command, at, expected + 1, expected_delivery + 1)
            connection.execute(text(UPSERT_POLICY), values)
            connection.execute(
                text(
                    "UPDATE team_delivery_profiles SET wip_limit=:wip,"
                    "policy_version=:delivery_version,"
                    "updated_at=:at WHERE unit_id=:unit"
                ),
                values,
            )
            _record_command(connection, command, unit_id, expected + 1, at)
            return _load_policy(connection, unit_id)

    def _create_export(self, command: WorkspaceCommand) -> WorkspaceExport:
        with (
            self._engine.connect().execution_options(isolation_level="SERIALIZABLE") as connection,
            connection.begin(),
        ):
            at = transaction_time(connection)
            unit_id = UUID(str(command.payload["unit_id"]))
            scope = (
                WorkspaceScope.DESCENDANTS
                if bool(command.payload["include_descendants"])
                else WorkspaceScope.DIRECT
            )
            grant = resolve_workspace_authority(
                connection,
                command.actor_user_id,
                unit_id,
                ManagementAction.WORKSPACE_EXPORT,
                scope,
                at,
                lock=True,
            )
            _match_grant(command, grant.grant_id, grant.grant_version)
            replay = _export_replay(connection, command)
            if replay is not None:
                return replay
            recent_exports = connection.execute(
                text(
                    "SELECT count(*) FROM workspace_export_jobs "
                    "WHERE actor_user_id=:actor AND created_at>:since"
                ),
                {"actor": command.actor_user_id, "since": at - timedelta(hours=1)},
            ).scalar_one()
            if int(recent_exports) >= 5:
                raise WorkspaceOperationsConflict("workspace export hourly limit reached")
            report = analytics(connection, command.actor_user_id, unit_id, scope)
            snapshot = {
                "generated_at": report.generated_at.isoformat(),
                "scope": report.scope.value,
                "privacy_notice": report.privacy_notice,
                "metrics": [
                    {
                        "label": metric.label,
                        "period": metric.period,
                        "display": metric.display,
                        "suppressed": metric.suppressed,
                    }
                    for metric in report.metrics
                ],
            }
            export_id = UUID(str(command.payload["export_id"]))
            values = {
                "export": export_id,
                "actor": command.actor_user_id,
                "unit": unit_id,
                "descendants": scope is WorkspaceScope.DESCENDANTS,
                "grant": grant.grant_id,
                "grant_version": grant.grant_version,
                "command": command.command_id,
                "key": command.idempotency_key,
                "hash": command.request_hash,
                "rows": len(report.metrics),
                "snapshot": json.dumps(snapshot, separators=(",", ":"), sort_keys=True),
                "handling": "SYNTHETIC EXERCISE · AUTHORISED RECIPIENTS",
                "at": at,
                "expires": at + timedelta(hours=24),
            }
            connection.execute(text(INSERT_EXPORT), values)
            _append_evidence(connection, command, export_id, 1, at)
            return _export_row(connection, export_id)


def _policy_values(
    command: WorkspaceCommand, at: datetime, version: int, delivery_version: int
) -> dict[str, object]:
    return {
        "unit": UUID(str(command.payload["unit_id"])),
        "wip": int(str(command.payload["wip_limit"])),
        "service": int(str(command.payload["service_target_hours"])),
        "cadence": str(command.payload["planning_cadence"]),
        "weekday": int(str(command.payload["planning_weekday"])),
        "local_time": str(command.payload["planning_local_time"]),
        "duration": int(str(command.payload["planning_duration_minutes"])),
        "version": version,
        "delivery_version": delivery_version,
        "actor": command.actor_user_id,
        "at": at,
    }


def _match_grant(command: WorkspaceCommand, grant_id: UUID, grant_version: int) -> None:
    if (
        UUID(str(command.payload["authorising_grant_id"])) != grant_id
        or int(str(command.payload["expected_grant_version"])) != grant_version
    ):
        raise WorkspaceOperationsDenied


def _command_replay(connection: Connection, command: WorkspaceCommand) -> RowMapping | None:
    row = (
        connection.execute(
            text(
                "SELECT request_hash FROM workspace_productivity_commands "
                "WHERE actor_user_id=:actor AND idempotency_key=:key FOR UPDATE"
            ),
            {"actor": command.actor_user_id, "key": command.idempotency_key},
        )
        .mappings()
        .first()
    )
    if row is not None and row["request_hash"] != command.request_hash:
        raise WorkspaceOperationsConflict("idempotency key was already used")
    return row


def _export_replay(connection: Connection, command: WorkspaceCommand) -> WorkspaceExport | None:
    row = (
        connection.execute(
            text(
                "SELECT * FROM workspace_export_jobs WHERE actor_user_id=:actor "
                "AND idempotency_key=:key FOR UPDATE"
            ),
            {"actor": command.actor_user_id, "key": command.idempotency_key},
        )
        .mappings()
        .first()
    )
    if row is not None and row["request_hash"] != command.request_hash:
        raise WorkspaceOperationsConflict("idempotency key was already used")
    return None if row is None else _decode_export(row)


def _record_command(
    connection: Connection,
    command: WorkspaceCommand,
    aggregate: UUID,
    version: int,
    at: datetime,
) -> None:
    connection.execute(
        text(INSERT_COMMAND),
        {
            "command": command.command_id,
            "key": command.idempotency_key,
            "hash": command.request_hash,
            "actor": command.actor_user_id,
            "operation": command.operation,
            "result": json.dumps({"unit_id": str(aggregate), "version": version}),
            "at": at,
        },
    )
    _append_evidence(connection, command, aggregate, version, at)


def _append_evidence(
    connection: Connection,
    command: WorkspaceCommand,
    aggregate: UUID,
    version: int,
    at: datetime,
) -> None:
    event = uuid5(NAMESPACE_URL, f"coeus:workspace-operations:{command.command_id}")
    payload = json.dumps(
        {"aggregate_id": str(aggregate), "operation": command.operation, "version": version}
    )
    values = {
        "event": event,
        "type": f"workspace_{command.operation}",
        "at": at,
        "actor": command.actor_user_id,
        "aggregate": aggregate,
        "version": version,
        "payload": payload,
    }
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id,event_type,occurred_at,actor_user_id,metadata) "
            "VALUES (:event,:type,:at,:actor,CAST(:payload AS jsonb))"
        ),
        values,
    )
    connection.execute(
        text(
            "INSERT INTO coeus_outbox"
            "(event_id,aggregate_id,aggregate_version,event_type,payload) "
            "VALUES (:event,:aggregate,:version,:type,CAST(:payload AS jsonb))"
        ),
        values,
    )


def _load_policy(connection: Connection, unit_id: UUID) -> WorkspacePolicy:
    from coeus.persistence.workspace_operations_queries import _POLICY

    return _policy_row(connection.execute(text(_POLICY), {"unit": unit_id}).mappings().one())


def _export_row(connection: Connection, export_id: UUID) -> WorkspaceExport:
    return _decode_export(
        connection.execute(
            text("SELECT * FROM workspace_export_jobs WHERE export_id=:export"),
            {"export": export_id},
        )
        .mappings()
        .one()
    )


def _decode_export(row: RowMapping) -> WorkspaceExport:
    return WorkspaceExport(
        UUID(str(row["export_id"])),
        UUID(str(row["actor_user_id"])),
        UUID(str(row["unit_id"])),
        bool(row["include_descendants"]),
        str(row["state"]),
        int(row["row_count"]),
        row["created_at"],
        row["expires_at"],
    )
