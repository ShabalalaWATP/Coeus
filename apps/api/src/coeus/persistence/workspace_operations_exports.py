"""Authority-rechecked download of pinned workspace export snapshots."""

import csv
import io
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation import ManagementAction
from coeus.domain.workspace_operations import (
    WorkspaceExport,
    WorkspaceOperationsConflict,
    WorkspaceOperationsDenied,
    WorkspaceScope,
)
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.workspace_operations_authority import resolve_workspace_authority
from coeus.persistence.workspace_operations_writes import _decode_export


def get_export(connection: Connection, actor: UUID, export_id: UUID) -> WorkspaceExport:
    row = (
        connection.execute(
            text(
                "SELECT * FROM workspace_export_jobs WHERE export_id=:export "
                "AND actor_user_id=:actor"
            ),
            {"export": export_id, "actor": actor},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise WorkspaceOperationsDenied
    at = transaction_time(connection)
    if row["expires_at"] <= at:
        raise WorkspaceOperationsDenied
    scope = WorkspaceScope.DESCENDANTS if row["include_descendants"] else WorkspaceScope.DIRECT
    grant = resolve_workspace_authority(
        connection, actor, UUID(str(row["unit_id"])), ManagementAction.WORKSPACE_EXPORT, scope, at
    )
    if grant.grant_id != row["authorising_grant_id"]:
        raise WorkspaceOperationsDenied
    return _decode_export(row)


def export_csv(connection: Connection, actor: UUID, export_id: UUID) -> bytes:
    get_export(connection, actor, export_id)
    row = (
        connection.execute(
            text(
                "SELECT snapshot_payload,handling_marking FROM workspace_export_jobs "
                "WHERE export_id=:export"
            ),
            {"export": export_id},
        )
        .mappings()
        .one()
    )
    snapshot = row["snapshot_payload"]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(["ISTARI TEAM OPERATIONAL EXPORT", snapshot["generated_at"]])
    writer.writerow(["handling", row["handling_marking"]])
    writer.writerow(["reviewed scope", snapshot["scope"]])
    writer.writerow(["privacy", snapshot["privacy_notice"]])
    writer.writerow(["scope", "metric", "period", "value"])
    for item in snapshot["metrics"]:
        writer.writerow([snapshot["scope"], item["label"], item["period"], item["display"]])
    encoded = output.getvalue().encode("utf-8-sig")
    if len(encoded) > 10 * 1024 * 1024:
        raise WorkspaceOperationsConflict("workspace export exceeds the size limit")
    return encoded
