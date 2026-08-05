"""Stateless preconditions for an exact cutover activation.

Kept apart from the store so the transactional operations stay readable: every
function here decides whether a step is permitted and raises if it is not,
without owning a connection or a transaction of its own.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverManifest,
    CutoverSlice,
    CutoverSliceStatus,
)
from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE
from coeus.persistence.cutover_activation_sql import INSERT_MANIFEST, INSERT_RELEASE, LOCK_PREVIEW


def require_manifest_evidence(
    manifest: CutoverManifest, slice: CutoverSlice, snapshot_hash: str, parity: bool
) -> None:
    expected = {
        CutoverSlice.ORGANISATION: manifest.organisation_parity_hash,
        CutoverSlice.CALENDAR: manifest.calendar_parity_hash,
        CutoverSlice.TASK_CAPACITY: manifest.task_capacity_parity_hash,
    }[slice]
    if (
        not parity
        or expected != snapshot_hash
        or manifest.routing_evaluation_release != ROUTING_RELATIONAL_CAPACITY_RELEASE
    ):
        raise ValueError("manifest parity evidence does not match the current projection")


def require_execution_people(
    approvals: tuple[RowMapping, ...], proposed_by: UUID, executor: UUID
) -> None:
    if len(approvals) != 2:
        raise ValueError("both exact approval records are required")
    actors = {row["approved_by_user_id"] for row in approvals}
    roles = {row["approval_role"] for row in approvals}
    if roles != {item.value for item in CutoverApprovalRole}:
        raise ValueError("both approval roles are required")
    if len(actors) != 2 or executor in actors or executor == proposed_by:
        raise PermissionError("proposer, approvers and executor must be distinct")


def lock_release(
    connection: Connection, manifest: CutoverManifest, actor: UUID, at: datetime
) -> None:
    existing = connection.execute(
        text("SELECT candidate_hash FROM organisation_cutover_release WHERE singleton FOR UPDATE")
    ).scalar_one_or_none()
    if existing is not None and existing != manifest.candidate_hash:
        raise ValueError("another exact cutover candidate is already bound")
    connection.execute(text(INSERT_MANIFEST), manifest_bindings(manifest, actor, at))
    connection.execute(text(INSERT_RELEASE), {"candidate": manifest.candidate_hash, "at": at})


def lock_preview(
    connection: Connection,
    slice: CutoverSlice,
    candidate: str,
    preview: str,
    occurred_at: datetime,
) -> RowMapping:
    row = (
        connection.execute(text(LOCK_PREVIEW), {"candidate": candidate, "slice": slice.value})
        .mappings()
        .one_or_none()
    )
    if (
        row is None
        or row["preview_hash"] != preview
        or row["status"]
        not in (CutoverSliceStatus.PREVIEWED.value, CutoverSliceStatus.APPROVED.value)
        or row["preview_expires_at"] <= occurred_at
    ):
        raise ValueError("the exact preview is missing, stale or expired")
    return row


def approval_bindings(candidate: str, slice: CutoverSlice, at: datetime) -> dict[str, object]:
    return {"candidate": candidate, "slice": slice.value, "at": at}


def manifest_bindings(manifest: CutoverManifest, actor: UUID, at: datetime) -> dict[str, object]:
    return {"candidate": manifest.candidate_hash, "actor": actor, "at": at, **manifest.__dict__}
