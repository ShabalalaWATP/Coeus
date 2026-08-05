"""Atomic PostgreSQL commands for the disabled organisation grant authority."""

import json
from dataclasses import replace
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.domain.organisation import ManagementAction, OrganisationManagementGrant
from coeus.domain.organisation_authority import (
    GrantCommandResult,
    OrganisationAuthorityConflict,
    OrganisationAuthorityDenied,
    OrganisationIdempotencyConflict,
    RevokeManagementGrantCommand,
)
from coeus.persistence import organisation_authority_sql as sql
from coeus.persistence.organisation_authority_validation import (
    grant_row as _grant_row,
)
from coeus.persistence.organisation_authority_validation import (
    lock_lineages as _lock_lineages,
)
from coeus.persistence.organisation_authority_validation import (
    transaction_time as _transaction_time,
)
from coeus.persistence.organisation_authority_validation import (
    validate_delegation as _validate_delegation,
)
from coeus.persistence.organisation_authority_validation import (
    validate_lineage as _validate_lineage,
)
from coeus.persistence.organisation_grant_rows import dataclass_params as _params


class PostgresOrganisationGrantCommandStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def replay_result(
        self,
        *,
        command_id: UUID,
        idempotency_key: str,
        request_hash: str,
        command_type: str,
        actor_user_id: UUID,
        grant_id: UUID,
    ) -> GrantCommandResult | None:
        with self._engine.begin() as connection:
            row = _load_command(connection, command_id, idempotency_key)
            return _replay(
                row,
                command_id,
                idempotency_key,
                request_hash,
                command_type,
                actor_user_id,
                grant_id,
            )

    def create_grant(
        self,
        grant: OrganisationManagementGrant,
        *,
        command_id: UUID,
        idempotency_key: str,
        request_hash: str,
        actor_user_id: UUID,
        management_grant_id: UUID,
        source_expected_version: int,
        occurred_at: datetime,
    ) -> GrantCommandResult:
        del occurred_at
        with self._engine.begin() as connection:
            transaction_time = _transaction_time(connection)
            grant = replace(grant, valid_from=transaction_time)
            _command_locks(connection, idempotency_key, grant.grant_id)
            replay = _replay(
                _load_command(connection, command_id, idempotency_key),
                command_id,
                idempotency_key,
                request_hash,
                "create",
                actor_user_id,
                grant.grant_id,
            )
            if replay is not None:
                return replay
            if (
                connection.execute(
                    text("SELECT 1 FROM team_management_grants WHERE grant_id = :grant_id"),
                    {"grant_id": grant.grant_id},
                ).first()
                is not None
            ):
                raise OrganisationAuthorityConflict("grant identity already exists")
            if grant.source_grant_id is None:
                raise OrganisationAuthorityDenied("delegated grant requires a source")
            _lock_lineages(connection, (management_grant_id, grant.source_grant_id))
            _validate_lineage(
                connection,
                management_grant_id,
                actor_user_id,
                grant.root_unit_id,
                ManagementAction.GRANT_MANAGE,
                transaction_time,
            )
            source = _validate_lineage(
                connection,
                grant.source_grant_id,
                actor_user_id,
                grant.root_unit_id,
                grant.action,
                transaction_time,
            )
            if int(str(source["version"])) != source_expected_version:
                raise OrganisationAuthorityConflict("source grant version is no longer current")
            _validate_delegation(source, grant)
            inserted = connection.execute(text(sql.INSERT_GRANT), _params(grant)).first()
            if inserted is None:
                raise OrganisationAuthorityConflict("grant could not be created")
            _write_command(
                connection,
                command_id,
                idempotency_key,
                request_hash,
                "create",
                actor_user_id,
                grant.grant_id,
                management_grant_id,
                1,
                transaction_time,
            )
            _advance_epochs(
                connection, {(grant.manager_user_id, grant.root_unit_id)}, transaction_time
            )
            _append_evidence(
                connection,
                command_id,
                grant.grant_id,
                1,
                "organisation_grant_created",
                actor_user_id,
                transaction_time,
                1,
            )
            return GrantCommandResult(grant.grant_id, 1)

    def revoke_grant(
        self,
        command: RevokeManagementGrantCommand,
        *,
        request_hash: str,
        management_grant_id: UUID,
        occurred_at: datetime,
    ) -> GrantCommandResult:
        del occurred_at
        with self._engine.begin() as connection:
            transaction_time = _transaction_time(connection)
            _command_locks(connection, command.idempotency_key, command.grant_id)
            replay = _replay(
                _load_command(connection, command.command_id, command.idempotency_key),
                command.command_id,
                command.idempotency_key,
                request_hash,
                "revoke",
                command.actor_user_id,
                command.grant_id,
            )
            if replay is not None:
                return replay
            _lock_lineages(connection, (management_grant_id, command.grant_id))
            target = _grant_row(connection, command.grant_id)
            if target is None:
                raise OrganisationAuthorityConflict("grant no longer exists")
            _validate_lineage(
                connection,
                management_grant_id,
                command.actor_user_id,
                UUID(str(target["root_unit_id"])),
                ManagementAction.GRANT_MANAGE,
                transaction_time,
            )
            if int(str(target["version"])) != command.expected_version or target["revoked_at"]:
                raise OrganisationAuthorityConflict("grant version is no longer current")
            if target["valid_until"] is not None and target["valid_until"] <= transaction_time:
                raise OrganisationAuthorityConflict("an expired grant cannot be revoked")
            version = connection.execute(
                text(sql.REVOKE_GRANT),
                {
                    "grant_id": command.grant_id,
                    "expected_version": command.expected_version,
                    "occurred_at": transaction_time,
                    "actor_user_id": command.actor_user_id,
                    "reason": command.reason,
                },
            ).scalar_one_or_none()
            if version is None:
                raise OrganisationAuthorityConflict("grant version is no longer current")
            affected_rows = connection.execute(
                text(sql.AFFECTED_GRANTS), {"grant_id": command.grant_id}
            ).mappings()
            affected = {
                (UUID(str(row["manager_user_id"])), UUID(str(row["root_unit_id"])))
                for row in affected_rows
            }
            _advance_epochs(connection, affected, transaction_time)
            _write_command(
                connection,
                command.command_id,
                command.idempotency_key,
                request_hash,
                "revoke",
                command.actor_user_id,
                command.grant_id,
                management_grant_id,
                int(version),
                transaction_time,
            )
            _append_evidence(
                connection,
                command.command_id,
                command.grant_id,
                int(version),
                "organisation_grant_revoked",
                command.actor_user_id,
                transaction_time,
                len(affected),
            )
            return GrantCommandResult(command.grant_id, int(version))


def _command_locks(connection: Connection, key: str, grant_id: UUID) -> None:
    for value in sorted((f"idempotency:{key}", f"grant:{grant_id}")):
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"), {"value": value}
        )


def _load_command(connection: Connection, command_id: UUID, key: str) -> RowMapping | None:
    rows = (
        connection.execute(
            text(sql.LOAD_COMMAND), {"command_id": command_id, "idempotency_key": key}
        )
        .mappings()
        .all()
    )
    if len(rows) > 1:
        raise OrganisationIdempotencyConflict("command and idempotency key identify different rows")
    return rows[0] if rows else None


def _replay(
    row: RowMapping | None,
    command_id: UUID,
    key: str,
    request_hash: str,
    command_type: str,
    actor_id: UUID,
    grant_id: UUID,
) -> GrantCommandResult | None:
    if row is None:
        return None
    matches = (
        UUID(str(row["command_id"])) == command_id
        and str(row["idempotency_key"]) == key
        and str(row["request_hash"]) == request_hash
        and str(row["command_type"]) == command_type
        and UUID(str(row["actor_user_id"])) == actor_id
        and UUID(str(row["grant_id"])) == grant_id
    )
    if not matches:
        raise OrganisationIdempotencyConflict("idempotency identity already has another payload")
    return GrantCommandResult(grant_id, int(str(row["result_version"])), True)


def _write_command(
    connection: Connection,
    command_id: UUID,
    key: str,
    request_hash: str,
    command_type: str,
    actor_id: UUID,
    grant_id: UUID,
    authorising_id: UUID,
    version: int,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(sql.INSERT_COMMAND),
        {
            "command_id": command_id,
            "idempotency_key": key,
            "request_hash": request_hash,
            "command_type": command_type,
            "actor_user_id": actor_id,
            "grant_id": grant_id,
            "authorising_grant_id": authorising_id,
            "result_version": version,
            "occurred_at": occurred_at,
        },
    ).one()


def _advance_epochs(
    connection: Connection, affected: set[tuple[UUID, UUID]], occurred_at: datetime
) -> None:
    for principal_id, scope_unit_id in sorted(
        affected, key=lambda item: (str(item[0]), str(item[1]))
    ):
        connection.execute(
            text(sql.ADVANCE_EPOCH),
            {
                "principal_id": principal_id,
                "scope_unit_id": scope_unit_id,
                "occurred_at": occurred_at,
            },
        )


def _append_evidence(
    connection: Connection,
    command_id: UUID,
    grant_id: UUID,
    version: int,
    event_type: str,
    actor_id: UUID,
    occurred_at: datetime,
    affected_count: int,
) -> None:
    payload = json.dumps(
        {"grant_id": str(grant_id), "version": version, "affected_grants": affected_count},
        sort_keys=True,
    )
    values = {
        "event_id": uuid5(NAMESPACE_URL, f"coeus:organisation:{event_type}:{command_id}"),
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_user_id": str(actor_id),
        "payload": payload,
        "grant_id": grant_id,
        "version": version,
    }
    connection.execute(text(sql.INSERT_AUDIT), values)
    connection.execute(text(sql.INSERT_OUTBOX), values)
