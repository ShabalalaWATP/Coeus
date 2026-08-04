"""Serializable, reviewed work-package dependency commands."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.work_package_dependencies import WorkPackageDependencyStore
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangePreview,
    DependencyChangeRequest,
    DependencyChangeResult,
    DependencyOperation,
    WorkPackageDependencyConflict,
    WorkPackageDependencyDenied,
    dependency_change_hash,
    validate_bounded_dependency_graph,
)
from coeus.persistence.organisation_authority_validation import transaction_time, validate_lineage
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.work_package_dependency_evidence import (
    append_dependency_evidence,
    dependency_history_values,
)
from coeus.persistence.work_package_dependency_sql import (
    ADD_DEPENDENCY,
    COMMANDS,
    DEPENDENCY,
    GRANT,
    GRAPH_EDGES,
    GRAPH_EDGES_FOR_UPDATE,
    GRAPH_PACKAGES,
    GRAPH_PACKAGES_FOR_UPDATE,
    INSERT_COMMAND,
    INSERT_HISTORY,
    LEAF_UNIT,
    PACKAGE,
    PACKAGE_FOR_UPDATE,
    REMOVE_DEPENDENCY,
    UPDATE_PACKAGE,
)

_ACTIVE_STATES = {"pending", "ready", "in_progress", "blocked"}


class PostgresWorkPackageDependencyStore(WorkPackageDependencyStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def preview(
        self, actor_user_id: UUID, request: DependencyChangeRequest
    ) -> DependencyChangePreview:
        with self._engine.begin() as connection:
            package, predecessor, active = _load_and_validate(
                connection, actor_user_id, request, lock=False
            )
            return _preview(actor_user_id, request, package, predecessor, active)

    def execute(self, command: ChangeDependencyCommand) -> DependencyChangeResult:
        return retry_serializable_once(lambda: self._execute_once(command))

    def _execute_once(self, command: ChangeDependencyCommand) -> DependencyChangeResult:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                replay = _replay(connection, command)
                if replay is not None:
                    return replay
                package, predecessor, active = _load_and_validate(
                    connection, command.actor_user_id, command.request, lock=True
                )
                preview = _preview(
                    command.actor_user_id, command.request, package, predecessor, active
                )
                if preview.preview_hash != command.preview_hash:
                    raise WorkPackageDependencyConflict("dependency preview is no longer current")
                return _apply(connection, command)
        finally:
            connection.close()


def _preview(
    actor_user_id: UUID,
    request: DependencyChangeRequest,
    package: RowMapping,
    predecessor: RowMapping,
    active: bool,
) -> DependencyChangePreview:
    return DependencyChangePreview(
        dependency_change_hash(actor_user_id, request),
        request.package_id,
        int(package["version"]),
        request.predecessor_package_id,
        int(predecessor["version"]),
        int(package["ownership_version"]),
        active,
        int(package["version"]) + 1,
    )


def _load_and_validate(
    connection: Connection,
    actor_user_id: UUID,
    request: DependencyChangeRequest,
    *,
    lock: bool,
) -> tuple[RowMapping, RowMapping, bool]:
    rows = tuple(
        connection.execute(
            text(PACKAGE_FOR_UPDATE if lock else PACKAGE),
            {"package_id": request.package_id, "predecessor_id": request.predecessor_package_id},
        ).mappings()
    )
    by_id = {row["package_id"]: row for row in rows}
    if len(by_id) != 2:
        raise WorkPackageDependencyDenied("work packages are unavailable")
    package, predecessor = by_id[request.package_id], by_id[request.predecessor_package_id]
    _validate_scope_and_versions(request, package, predecessor)
    occurred_at = transaction_time(connection)
    _validate_leaf_and_grant(connection, actor_user_id, request, occurred_at)
    active = (
        connection.execute(
            text(DEPENDENCY),
            {"package_id": request.package_id, "predecessor_id": request.predecessor_package_id},
        ).scalar_one_or_none()
        is not None
    )
    if request.operation is DependencyOperation.ADD and active:
        raise WorkPackageDependencyConflict("dependency already exists")
    if request.operation is DependencyOperation.REMOVE and not active:
        raise WorkPackageDependencyConflict("dependency does not exist")
    _validate_graph(connection, request, lock=lock)
    return package, predecessor, active


def _validate_scope_and_versions(
    request: DependencyChangeRequest, package: RowMapping, predecessor: RowMapping
) -> None:
    if (
        int(package["version"]) != request.expected_package_version
        or int(predecessor["version"]) != request.expected_predecessor_version
        or int(package["ownership_version"]) != request.expected_ownership_version
        or int(predecessor["ownership_version"]) != request.expected_ownership_version
    ):
        raise WorkPackageDependencyConflict("work-package evidence changed")
    scope = (package["ticket_id"], package["workflow_leg"], package["owning_unit_id"])
    if scope != (
        predecessor["ticket_id"],
        predecessor["workflow_leg"],
        predecessor["owning_unit_id"],
    ):
        raise WorkPackageDependencyDenied("dependencies require the same task, leg and team")
    if (
        package["owning_unit_id"] != request.unit_id
        or package["ownership_unit_id"] != request.unit_id
        or predecessor["ownership_unit_id"] != request.unit_id
        or package["ownership_state"] != "active"
        or predecessor["ownership_state"] != "active"
        or package["state"] not in _ACTIVE_STATES
        or predecessor["state"] not in _ACTIVE_STATES
    ):
        raise WorkPackageDependencyDenied("work packages are outside active assignment authority")


def _validate_leaf_and_grant(
    connection: Connection,
    actor_user_id: UUID,
    request: DependencyChangeRequest,
    occurred_at: datetime,
) -> None:
    if (
        connection.execute(
            text(LEAF_UNIT), {"unit_id": request.unit_id, "at": occurred_at}
        ).scalar_one_or_none()
        is None
    ):
        raise WorkPackageDependencyDenied("dependencies require an active leaf team")
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
        raise WorkPackageDependencyDenied("current task assignment authority is required")
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
        raise WorkPackageDependencyDenied("current task assignment authority is required") from exc


def _validate_graph(
    connection: Connection, request: DependencyChangeRequest, *, lock: bool
) -> None:
    params = {"ticket_id": None, "workflow_leg": None}
    package = (
        connection.execute(
            text("SELECT ticket_id,workflow_leg FROM canonical_work_packages WHERE package_id=:id"),
            {"id": request.package_id},
        )
        .mappings()
        .one()
    )
    params.update(package)
    package_rows = tuple(
        connection.execute(text(GRAPH_PACKAGES_FOR_UPDATE if lock else GRAPH_PACKAGES), params)
    )
    edge_rows = tuple(
        connection.execute(text(GRAPH_EDGES_FOR_UPDATE if lock else GRAPH_EDGES), params)
    )
    package_ids = tuple(row[0] for row in package_rows)
    edges = [(row[0], row[1]) for row in edge_rows]
    edge = (request.package_id, request.predecessor_package_id)
    if request.operation is DependencyOperation.ADD:
        edges.append(edge)
    else:
        edges.remove(edge)
    validate_bounded_dependency_graph(package_ids, tuple(edges))


def _apply(connection: Connection, command: ChangeDependencyCommand) -> DependencyChangeResult:
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
    active = request.operation is DependencyOperation.ADD
    connection.execute(
        text(ADD_DEPENDENCY if active else REMOVE_DEPENDENCY),
        {
            "package_id": request.package_id,
            "predecessor_id": request.predecessor_package_id,
            "actor_id": command.actor_user_id,
            "at": occurred_at,
        },
    )
    connection.execute(
        text(INSERT_HISTORY), dependency_history_values(command, package_version, occurred_at)
    )
    connection.execute(
        text(INSERT_COMMAND), _command_values(command, package_version, active, occurred_at)
    )
    append_dependency_evidence(connection, command, package_version, occurred_at)
    return DependencyChangeResult(
        request.package_id, package_version, request.predecessor_package_id, active, False
    )


def _command_values(
    command: ChangeDependencyCommand, package_version: int, active: bool, occurred_at: datetime
) -> dict[str, object]:
    request = command.request
    return {
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "request_hash": dependency_change_hash(command.actor_user_id, request),
        "package_id": request.package_id,
        "predecessor_id": request.predecessor_package_id,
        "actor_id": command.actor_user_id,
        "operation": request.operation.value,
        "expected_package_version": request.expected_package_version,
        "expected_predecessor_version": request.expected_predecessor_version,
        "expected_ownership_version": request.expected_ownership_version,
        "expected_grant_version": request.expected_grant_version,
        "result_package_version": package_version,
        "result_active": active,
        "at": occurred_at,
    }


def _replay(
    connection: Connection, command: ChangeDependencyCommand
) -> DependencyChangeResult | None:
    rows = tuple(
        connection.execute(
            text(COMMANDS),
            {"command_id": command.command_id, "idempotency_key": command.idempotency_key},
        ).mappings()
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise WorkPackageDependencyConflict("dependency command identities conflict")
    row, request = rows[0], command.request
    if (
        row["request_hash"] != dependency_change_hash(command.actor_user_id, request)
        or row["actor_user_id"] != command.actor_user_id
        or row["package_id"] != request.package_id
        or row["predecessor_package_id"] != request.predecessor_package_id
        or row["operation"] != request.operation.value
    ):
        raise WorkPackageDependencyConflict("dependency command identity was reused")
    return DependencyChangeResult(
        request.package_id,
        int(row["result_package_version"]),
        request.predecessor_package_id,
        bool(row["result_active"]),
        True,
    )
