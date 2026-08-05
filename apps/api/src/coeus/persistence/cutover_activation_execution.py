"""Atomic writer fencing and final eligibility for cutover activation."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.cutover_activation import CutoverSlice
from coeus.persistence.cutover_activation_evidence import (
    digest,
    record_audit_outbox,
    record_evidence,
)
from coeus.persistence.cutover_activation_snapshots import CutoverSnapshot, capture_snapshot
from coeus.persistence.cutover_activation_sql import (
    ACTIVATE_SLICE,
    AUTHORITATIVE_FENCE,
    COMPLETE_CHECKPOINT,
    ELIGIBLE,
    FENCE_SOURCE,
    INSERT_CHECKPOINT,
    INSERT_CHECKPOINT_EVENT,
    INSERT_RECOVERY,
    LOCK_CHECKPOINT,
    PREDECESSORS,
    RENEW_CHECKPOINT,
    UPSERT_FENCE,
)


def prepare_activation(
    connection: Connection,
    slice: CutoverSlice,
    candidate: str,
    actor: UUID,
    occurred_at: datetime,
    snapshot: CutoverSnapshot,
) -> tuple[UUID, UUID]:
    owner, checkpoint = uuid4(), uuid4()
    predecessors = {
        CutoverSlice.ORGANISATION: (),
        CutoverSlice.CALENDAR: (CutoverSlice.ORGANISATION.value,),
        CutoverSlice.TASK_CAPACITY: (
            CutoverSlice.ORGANISATION.value,
            CutoverSlice.CALENDAR.value,
        ),
    }[slice]
    active = connection.execute(
        text(PREDECESSORS),
        {"candidate": candidate, "predecessors": list(predecessors)},
    ).scalar_one()
    if int(active) != len(predecessors):
        raise ValueError("cutover slice predecessors are not active")
    existing = (
        connection.execute(text(LOCK_CHECKPOINT), {"candidate": candidate, "slice": slice.value})
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        return _resume_checkpoint(connection, existing, slice, candidate, actor, occurred_at)
    connection.execute(
        text(UPSERT_FENCE),
        {
            "slice": slice.value,
            "candidate": candidate,
            "owner": owner,
            "actor": actor,
            "at": occurred_at,
        },
    )
    connection.execute(
        text(INSERT_CHECKPOINT),
        {
            "id": checkpoint,
            "candidate": candidate,
            "slice": slice.value,
            "source_count": snapshot.source_count,
            "target_count": snapshot.target_count,
            "source": snapshot.source_hash,
            "target": snapshot.target_hash,
            "lease": owner,
            "at": occurred_at,
        },
    )
    event_hash = digest({"checkpoint": checkpoint, "candidate": candidate, "slice": slice.value})
    _record_checkpoint_event(connection, checkpoint, 1, "started", actor, event_hash, occurred_at)
    return checkpoint, owner


def finish_activation(
    connection: Connection,
    slice: CutoverSlice,
    candidate: str,
    actor: UUID,
    occurred_at: datetime,
    snapshot: CutoverSnapshot,
    checkpoint: UUID,
    lease: UUID,
) -> None:
    current = (
        connection.execute(text(LOCK_CHECKPOINT), {"candidate": candidate, "slice": slice.value})
        .mappings()
        .one()
    )
    if current["checkpoint_id"] != checkpoint or current["lease_token"] != lease:
        raise ValueError("cutover checkpoint lease changed")
    connection.execute(text("SET LOCAL lock_timeout = '5s'"))
    _lock_source(connection, slice)
    connection.execute(
        text(FENCE_SOURCE),
        {"slice": slice.value, "lease": lease, "at": occurred_at},
    )
    final = capture_snapshot(connection, slice)
    converged = capture_snapshot(connection, slice)
    if not final.parity or final != converged or final.source_hash != snapshot.source_hash:
        raise ValueError("visibility changed while source writers were fenced")
    activation_hash = digest(
        {
            "candidate": candidate,
            "slice": slice.value,
            "visibility": final.visibility_hash,
            "checkpoint": checkpoint,
        }
    )
    connection.execute(text(COMPLETE_CHECKPOINT), {"id": checkpoint, "at": occurred_at})
    _record_checkpoint_event(
        connection,
        checkpoint,
        int(current["version"]) + 1,
        "completed",
        actor,
        activation_hash,
        occurred_at,
    )
    connection.execute(
        text(ACTIVATE_SLICE),
        {
            "candidate": candidate,
            "slice": slice.value,
            "actor": actor,
            "at": occurred_at,
        },
    )
    connection.execute(text(AUTHORITATIVE_FENCE), {"slice": slice.value, "at": occurred_at})
    record_evidence(
        connection,
        candidate_hash=candidate,
        slice=slice,
        kind="activation",
        evidence_hash=activation_hash,
        actor=actor,
        occurred_at=occurred_at,
        payload={"checkpoint_id": str(checkpoint)},
        snapshot=final,
    )
    record_audit_outbox(
        connection,
        event_type="organisation.cutover.slice_activated",
        candidate_hash=candidate,
        slice=slice,
        actor=actor,
        occurred_at=occurred_at,
        details={"evidence_hash": activation_hash},
    )


def _resume_checkpoint(
    connection: Connection,
    row: RowMapping,
    slice: CutoverSlice,
    candidate: str,
    actor: UUID,
    occurred_at: datetime,
) -> tuple[UUID, UUID]:
    if row["status"] != "running" or row["lease_expires_at"] > occurred_at:
        raise ValueError("cutover activation is already running or completed")
    checkpoint, owner = row["checkpoint_id"], uuid4()
    prior = digest(dict(row))
    connection.execute(
        text(RENEW_CHECKPOINT),
        {"id": checkpoint, "lease": owner, "at": occurred_at},
    )
    connection.execute(
        text(UPSERT_FENCE),
        {
            "slice": slice.value,
            "candidate": candidate,
            "owner": owner,
            "actor": actor,
            "at": occurred_at,
        },
    )
    result = digest({"checkpoint": checkpoint, "lease": owner, "status": "running"})
    connection.execute(
        text(INSERT_RECOVERY),
        {
            "recovery": uuid4(),
            "candidate": candidate,
            "slice": slice.value,
            "id": checkpoint,
            "actor": actor,
            "prior": prior,
            "result": result,
            "at": occurred_at,
        },
    )
    _record_checkpoint_event(
        connection,
        checkpoint,
        int(row["version"]) + 1,
        "resumed",
        actor,
        result,
        occurred_at,
    )
    return checkpoint, owner


def _record_checkpoint_event(
    connection: Connection,
    checkpoint: UUID,
    version: int,
    event_type: str,
    actor: UUID,
    evidence_hash: str,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(INSERT_CHECKPOINT_EVENT),
        {
            "event": uuid4(),
            "id": checkpoint,
            "version": version,
            "type": event_type,
            "actor": actor,
            "hash": evidence_hash,
            "at": occurred_at,
        },
    )


def _lock_source(connection: Connection, slice: CutoverSlice) -> None:
    if slice is CutoverSlice.TASK_CAPACITY:
        connection.execute(text("SELECT ticket_id FROM coeus_ticket_aggregates FOR UPDATE"))
        return
    namespace = "teams" if slice is CutoverSlice.ORGANISATION else "team_calendar"
    connection.execute(
        text("SELECT namespace FROM coeus_state WHERE namespace=:namespace FOR UPDATE"),
        {"namespace": namespace},
    )


def candidate_is_eligible(
    connection: Connection,
    candidate: str,
    source_revision: str | None,
    routing_release: str | None,
) -> bool:
    from coeus.persistence.cutover_activation_snapshots import require_current_schema

    require_current_schema(connection)
    row = connection.execute(text(ELIGIBLE), {"candidate": candidate}).mappings().one_or_none()
    if row is None:
        return False
    eligible = bool(
        int(row["active_slices"]) == len(CutoverSlice)
        and int(row["authoritative_fences"]) == len(CutoverSlice)
        and (source_revision is None or row["source_revision"] == source_revision)
        and (routing_release is None or row["routing_evaluation_release"] == routing_release)
    )
    if not eligible:
        return False
    snapshots = tuple(capture_snapshot(connection, slice) for slice in CutoverSlice)
    hashes = (
        row["organisation_parity_hash"],
        row["calendar_parity_hash"],
        row["task_capacity_parity_hash"],
    )
    return all(
        item.parity and item.source_hash == expected
        for item, expected in zip(snapshots, hashes, strict=True)
    )
