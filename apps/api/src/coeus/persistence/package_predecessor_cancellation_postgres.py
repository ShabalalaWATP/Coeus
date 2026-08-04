"""Serializable predecessor cancellation with complete dependant dispositions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.package_predecessor_cancellation import (
    PredecessorCancellationStore,
)
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    DependantDisposition,
    DependantDispositionAction,
    PredecessorCancellationConflict,
    PredecessorCancellationDenied,
    PredecessorCancellationPreview,
    PredecessorCancellationRequest,
    PredecessorCancellationResult,
    cancellation_hash,
)
from coeus.domain.work_package_dependencies import validate_bounded_dependency_graph
from coeus.persistence.organisation_authority_validation import transaction_time, validate_lineage
from coeus.persistence.package_predecessor_cancellation_commands import (
    lock_cancellation_identities,
    replay_cancellation,
)
from coeus.persistence.package_predecessor_cancellation_evidence import (
    append_cancellation_evidence,
    append_cancellation_history,
)
from coeus.persistence.package_predecessor_cancellation_sql import (
    BUMP_PACKAGE,
    CANCEL_PACKAGE,
    DELETE_EDGE,
    GRANT,
    GRAPH,
    INSERT_EDGE,
    PACKAGE,
)
from coeus.persistence.serializable_retry import retry_serializable_once


class PostgresPredecessorCancellationStore(PredecessorCancellationStore):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def preview(
        self, actor_user_id: UUID, request: PredecessorCancellationRequest
    ) -> PredecessorCancellationPreview:
        with self._engine.begin() as connection:
            package = _load_and_validate(connection, actor_user_id, request, lock=False)
            return _preview(actor_user_id, request, package)

    def execute(self, command: CancelPredecessorCommand) -> PredecessorCancellationResult:
        return retry_serializable_once(lambda: self._execute_once(command))

    def _execute_once(self, command: CancelPredecessorCommand) -> PredecessorCancellationResult:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                lock_cancellation_identities(connection, command)
                replay = replay_cancellation(connection, command)
                if replay is not None:
                    return replay
                package = _load_and_validate(
                    connection, command.actor_user_id, command.request, lock=True
                )
                if (
                    _preview(command.actor_user_id, command.request, package).preview_hash
                    != command.preview_hash
                ):
                    raise PredecessorCancellationConflict(
                        "predecessor cancellation preview is no longer current"
                    )
                return _apply(connection, command, package)
        finally:
            connection.close()


def _load_and_validate(
    connection: Connection,
    actor_user_id: UUID,
    request: PredecessorCancellationRequest,
    *,
    lock: bool,
) -> RowMapping:
    package = (
        connection.execute(
            text(PACKAGE + (" FOR UPDATE OF package,ownership" if lock else "")),
            {"package_id": request.package_id},
        )
        .mappings()
        .first()
    )
    if package is None or package["owning_unit_id"] != request.unit_id:
        raise PredecessorCancellationDenied("work package is unavailable")
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"work-package-graph:{package['ticket_id']}:{package['workflow_leg']}"},
    )
    if (
        int(package["version"]) != request.expected_package_version
        or int(package["ownership_version"]) != request.expected_ownership_version
    ):
        raise PredecessorCancellationConflict("work package evidence changed")
    if package["state"] in {"complete", "cancelled"}:
        raise PredecessorCancellationConflict("work package is already terminal")
    if package["ownership_state"] != "active":
        raise PredecessorCancellationDenied("work package is unavailable")
    _validate_grant(connection, actor_user_id, request, transaction_time(connection))
    rows = _graph_rows(connection, package, lock)
    _validate_dispositions(request, package, rows)
    return package


def _validate_grant(
    connection: Connection,
    actor_user_id: UUID,
    request: PredecessorCancellationRequest,
    at: datetime,
) -> None:
    row = (
        connection.execute(
            text(GRANT),
            {"grant_id": request.authorising_grant_id, "actor_id": actor_user_id, "at": at},
        )
        .mappings()
        .first()
    )
    if row is None or int(row["version"]) != request.expected_grant_version:
        raise PredecessorCancellationDenied("current task assignment authority is required")
    try:
        validate_lineage(
            connection,
            row["grant_id"],
            actor_user_id,
            request.unit_id,
            ManagementAction.TASK_ASSIGN,
            at,
        )
    except OrganisationAuthorityDenied as exc:
        raise PredecessorCancellationDenied(
            "current task assignment authority is required"
        ) from exc


def _graph_rows(connection: Connection, package: RowMapping, lock: bool) -> tuple[RowMapping, ...]:
    if lock:
        connection.execute(
            text(
                "SELECT package_id FROM canonical_work_packages "
                "WHERE ticket_id=:ticket_id AND workflow_leg=:leg "
                "ORDER BY package_id FOR UPDATE"
            ),
            {"ticket_id": package["ticket_id"], "leg": package["workflow_leg"]},
        )
    rows = tuple(
        connection.execute(
            text(GRAPH),
            {"ticket_id": package["ticket_id"], "leg": package["workflow_leg"]},
        ).mappings()
    )
    if len(rows) > 128:
        raise PredecessorCancellationDenied("work-package graph exceeds the review boundary")
    return rows


def _validate_dispositions(
    request: PredecessorCancellationRequest,
    package: RowMapping,
    rows: tuple[RowMapping, ...],
) -> None:
    by_id = {row["package_id"]: row for row in rows}
    edges = {
        (row["package_id"], predecessor)
        for row in rows
        for predecessor in (row["predecessors"] or ())
    }
    direct = {candidate for candidate, predecessor in edges if predecessor == request.package_id}
    supplied = {item.dependant_package_id for item in request.dispositions}
    if direct != supplied:
        raise PredecessorCancellationConflict("every dependant requires exactly one disposition")
    resulting = set(edges)
    for item in request.dispositions:
        dependant = by_id.get(item.dependant_package_id)
        if dependant is None or int(dependant["version"]) != item.expected_version:
            raise PredecessorCancellationConflict("dependant package evidence changed")
        resulting.discard((item.dependant_package_id, request.package_id))
        if item.action is DependantDispositionAction.CANCEL and any(
            predecessor == item.dependant_package_id for _, predecessor in resulting
        ):
            raise PredecessorCancellationConflict(
                "a cancelled dependant has unresolved downstream dependants"
            )
        if item.action is DependantDispositionAction.REPLACE:
            replacement = by_id.get(item.replacement_package_id)
            if (
                replacement is None
                or int(replacement["version"]) != item.expected_replacement_version
                or replacement["package_id"] == request.package_id
            ):
                raise PredecessorCancellationConflict("replacement package evidence changed")
            resulting.add((item.dependant_package_id, replacement["package_id"]))
    validate_bounded_dependency_graph(tuple(by_id), tuple(resulting))


def _preview(
    actor_user_id: UUID,
    request: PredecessorCancellationRequest,
    package: RowMapping,
) -> PredecessorCancellationPreview:
    return PredecessorCancellationPreview(
        cancellation_hash(actor_user_id, request),
        request.package_id,
        int(package["version"]),
        len(request.dispositions),
        int(package["version"]) + 1,
    )


def _apply(
    connection: Connection,
    command: CancelPredecessorCommand,
    package: RowMapping,
) -> PredecessorCancellationResult:
    at = transaction_time(connection)
    request = command.request
    counts = {action: 0 for action in DependantDispositionAction}
    connection.execute(
        text("SELECT set_config('coeus.predecessor_disposition',:package_id,true)"),
        {"package_id": str(request.package_id)},
    )
    for disposition in sorted(
        request.dispositions, key=lambda item: str(item.dependant_package_id)
    ):
        _apply_disposition(connection, command, disposition, at)
        counts[disposition.action] += 1
    version = int(
        connection.execute(
            text(CANCEL_PACKAGE),
            {
                "package_id": request.package_id,
                "version": request.expected_package_version,
                "at": at,
            },
        ).scalar_one()
    )
    append_cancellation_history(
        connection, command, request.package_id, version, "predecessor_cancelled", at
    )
    append_cancellation_evidence(connection, command, version, counts, at)
    return PredecessorCancellationResult(
        request.package_id,
        version,
        counts[DependantDispositionAction.CANCEL],
        counts[DependantDispositionAction.UNLINK],
        counts[DependantDispositionAction.REPLACE],
        False,
    )


def _apply_disposition(
    connection: Connection,
    command: CancelPredecessorCommand,
    item: DependantDisposition,
    at: datetime,
) -> None:
    if item.action is DependantDispositionAction.CANCEL:
        version = int(
            connection.execute(
                text(CANCEL_PACKAGE),
                {
                    "package_id": item.dependant_package_id,
                    "version": item.expected_version,
                    "at": at,
                },
            ).scalar_one()
        )
        append_cancellation_history(
            connection,
            command,
            item.dependant_package_id,
            version,
            "cancelled_with_predecessor",
            at,
        )
        return
    connection.execute(
        text(DELETE_EDGE),
        {
            "package_id": item.dependant_package_id,
            "predecessor_id": command.request.package_id,
        },
    )
    if item.action is DependantDispositionAction.REPLACE:
        connection.execute(
            text(INSERT_EDGE),
            {
                "package_id": item.dependant_package_id,
                "predecessor_id": item.replacement_package_id,
                "actor_id": command.actor_user_id,
                "at": at,
            },
        )
    version = int(
        connection.execute(
            text(BUMP_PACKAGE),
            {
                "package_id": item.dependant_package_id,
                "version": item.expected_version,
                "at": at,
            },
        ).scalar_one()
    )
    append_cancellation_history(
        connection,
        command,
        item.dependant_package_id,
        version,
        f"predecessor_{item.action.value}ed",
        at,
    )
