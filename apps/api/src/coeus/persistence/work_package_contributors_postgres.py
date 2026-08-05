"""Serializable, reviewed work-package contributor lifecycle."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.work_package_contributors import WorkPackageContributorStore
from coeus.domain.jioc_principals import PrincipalKind, principal_kind
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.work_package_contributors import (
    ChangeContributorCommand,
    ContributorChangePreview,
    ContributorChangeRequest,
    ContributorChangeResult,
    ContributorOperation,
    WorkPackageContributorConflict,
    WorkPackageContributorDenied,
    contributor_change_hash,
)
from coeus.persistence.identity_account_projection import active_analyst_role
from coeus.persistence.organisation_authority_validation import transaction_time, validate_lineage
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.work_package_contributor_capacity import reconcile_contributor_capacity
from coeus.persistence.work_package_contributor_evidence import (
    append_contributor_evidence,
    contributor_history_values,
)
from coeus.persistence.work_package_contributor_sql import (
    ACCOUNT,
    ADD_PARTICIPANT,
    COMMANDS,
    END_PARTICIPANT,
    GRANT,
    INSERT_COMMAND,
    INSERT_HISTORY,
    LEAF_UNIT,
    MEMBERSHIPS,
    PACKAGE,
    PACKAGE_FOR_UPDATE,
    PARTICIPANT,
    UPDATE_PACKAGE,
)


class PostgresWorkPackageContributorStore(WorkPackageContributorStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def preview(
        self, actor_user_id: UUID, request: ContributorChangeRequest
    ) -> ContributorChangePreview:
        with self._engine.begin() as connection:
            row, active = _load_and_validate(connection, actor_user_id, request, lock=False)
            return _preview(actor_user_id, request, row, active)

    def execute(self, command: ChangeContributorCommand) -> ContributorChangeResult:
        return retry_serializable_once(lambda: self._execute_once(command))

    def _execute_once(self, command: ChangeContributorCommand) -> ContributorChangeResult:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                replay = _replay(connection, command)
                if replay is not None:
                    return replay
                row, active = _load_and_validate(
                    connection, command.actor_user_id, command.request, lock=True
                )
                preview = _preview(command.actor_user_id, command.request, row, active)
                if preview.preview_hash != command.preview_hash:
                    raise WorkPackageContributorConflict("contributor preview is no longer current")
                return _apply(connection, command)
        finally:
            connection.close()


def _preview(
    actor_user_id: UUID,
    request: ContributorChangeRequest,
    row: RowMapping,
    active: bool,
) -> ContributorChangePreview:
    return ContributorChangePreview(
        contributor_change_hash(actor_user_id, request),
        request.package_id,
        int(row["version"]),
        int(row["ownership_version"]),
        request.contributor_user_id,
        active,
        int(row["version"]) + 1,
    )


def _load_and_validate(
    connection: Connection,
    actor_user_id: UUID,
    request: ContributorChangeRequest,
    *,
    lock: bool,
) -> tuple[RowMapping, bool]:
    row = (
        connection.execute(
            text(PACKAGE_FOR_UPDATE if lock else PACKAGE),
            {"package_id": request.package_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise WorkPackageContributorDenied("work package is unavailable")
    if (
        int(row["version"]) != request.expected_package_version
        or int(row["ownership_version"]) != request.expected_ownership_version
    ):
        raise WorkPackageContributorConflict("work package evidence changed")
    _validate_package_scope(request, row)
    occurred_at = transaction_time(connection)
    _validate_leaf(connection, request.unit_id, occurred_at)
    _validate_grant(connection, actor_user_id, request, occurred_at)
    _validate_account_and_posting(connection, request, occurred_at)
    active = _participant_active(connection, request)
    if request.operation is ContributorOperation.ADD and active:
        raise WorkPackageContributorConflict("contributor is already active")
    if request.operation is ContributorOperation.END and not active:
        raise WorkPackageContributorConflict("contributor is not active")
    return row, active


def _validate_package_scope(request: ContributorChangeRequest, row: RowMapping) -> None:
    if (
        row["owning_unit_id"] != request.unit_id
        or row["ownership_unit_id"] != request.unit_id
        or row["ownership_state"] != "active"
        or row["state"] not in {"pending", "ready", "in_progress", "blocked"}
    ):
        raise WorkPackageContributorDenied("work package is outside assignment authority")
    if row["accountable_user_id"] == request.contributor_user_id:
        raise WorkPackageContributorConflict("the accountable owner cannot also be a contributor")


def _validate_leaf(connection: Connection, unit_id: UUID, occurred_at: datetime) -> None:
    leaf = connection.execute(
        text(LEAF_UNIT), {"unit_id": unit_id, "at": occurred_at}
    ).scalar_one_or_none()
    if leaf is None:
        raise WorkPackageContributorDenied("contributors require an active leaf team")


def _validate_grant(
    connection: Connection,
    actor_user_id: UUID,
    request: ContributorChangeRequest,
    occurred_at: datetime,
) -> None:
    grant = (
        connection.execute(
            text(GRANT),
            {
                "grant_id": request.authorising_grant_id,
                "actor_id": actor_user_id,
                "unit_id": request.unit_id,
                "at": occurred_at,
            },
        )
        .mappings()
        .first()
    )
    if grant is None or int(grant["version"]) != request.expected_grant_version:
        raise WorkPackageContributorDenied("current task assignment authority is required")
    try:
        validate_lineage(
            connection,
            grant["grant_id"],
            actor_user_id,
            request.unit_id,
            ManagementAction.TASK_ASSIGN,
            occurred_at,
        )
    except OrganisationAuthorityDenied as exc:
        raise WorkPackageContributorDenied("current task assignment authority is required") from exc


def _validate_account_and_posting(
    connection: Connection,
    request: ContributorChangeRequest,
    occurred_at: datetime,
) -> None:
    if principal_kind(request.contributor_user_id) is not PrincipalKind.HUMAN:
        raise WorkPackageContributorDenied("contributors must be human analysts")
    account = (
        connection.execute(text(ACCOUNT), {"user_id": request.contributor_user_id})
        .mappings()
        .first()
    )
    if (
        account is None
        or not account["is_active"]
        or active_analyst_role() not in account["roles"]
        or int(account["credential_version"]) != request.expected_account_credential_version
        or str(account["source_hash"]) != request.expected_account_source_hash
    ):
        raise WorkPackageContributorDenied("contributor account evidence is not eligible")
    memberships = tuple(
        connection.execute(
            text(MEMBERSHIPS),
            {"user_id": request.contributor_user_id, "at": occurred_at},
        ).mappings()
    )
    if len(memberships) != 1:
        raise WorkPackageContributorDenied(
            "contributor requires exactly one assignment-eligible home posting"
        )
    membership = memberships[0]
    if (
        membership["membership_id"] != request.membership_id
        or membership["unit_id"] != request.unit_id
        or int(membership["version"]) != request.expected_membership_version
    ):
        raise WorkPackageContributorDenied("contributor home-posting evidence changed")


def _participant_active(connection: Connection, request: ContributorChangeRequest) -> bool:
    row = (
        connection.execute(
            text(PARTICIPANT),
            {"package_id": request.package_id, "user_id": request.contributor_user_id},
        )
        .mappings()
        .first()
    )
    return bool(row and row["active"])


def _apply(connection: Connection, command: ChangeContributorCommand) -> ContributorChangeResult:
    request = command.request
    occurred_at = transaction_time(connection)
    package_version = int(
        connection.execute(
            text(UPDATE_PACKAGE),
            {
                "package_id": request.package_id,
                "expected_version": request.expected_package_version,
                "at": occurred_at,
            },
        ).scalar_one()
    )
    active = request.operation is ContributorOperation.ADD
    connection.execute(
        text(ADD_PARTICIPANT if active else END_PARTICIPANT),
        {
            "package_id": request.package_id,
            "user_id": request.contributor_user_id,
            "at": occurred_at,
        },
    )
    reconcile_contributor_capacity(connection, command, package_version, occurred_at)
    connection.execute(
        text(INSERT_HISTORY),
        contributor_history_values(command, package_version, occurred_at),
    )
    connection.execute(
        text(INSERT_COMMAND),
        {
            "command_id": command.command_id,
            "idempotency_key": command.idempotency_key,
            "request_hash": contributor_change_hash(command.actor_user_id, request),
            "package_id": request.package_id,
            "contributor_user_id": request.contributor_user_id,
            "actor_user_id": command.actor_user_id,
            "operation": request.operation.value,
            "expected_package_version": request.expected_package_version,
            "result_package_version": package_version,
            "result_active": active,
            "occurred_at": occurred_at,
        },
    )
    append_contributor_evidence(connection, command, package_version, occurred_at)
    return ContributorChangeResult(
        request.package_id, package_version, request.contributor_user_id, active, False
    )


def _replay(
    connection: Connection, command: ChangeContributorCommand
) -> ContributorChangeResult | None:
    rows = tuple(
        connection.execute(
            text(COMMANDS),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise WorkPackageContributorConflict("contributor command identities conflict")
    row = rows[0]
    request = command.request
    if (
        row["request_hash"] != contributor_change_hash(command.actor_user_id, request)
        or row["actor_user_id"] != command.actor_user_id
        or row["package_id"] != request.package_id
        or row["contributor_user_id"] != request.contributor_user_id
        or row["operation"] != request.operation.value
    ):
        raise WorkPackageContributorConflict("contributor command identity was reused")
    return ContributorChangeResult(
        request.package_id,
        int(row["result_package_version"]),
        request.contributor_user_id,
        bool(row["result_active"]),
        True,
    )
