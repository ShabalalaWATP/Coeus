"""PostgreSQL store for exact-candidate organisation cutover activation."""

from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.application.ports.cutover_activation import CutoverActivationStore
from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverExecutionResult,
    CutoverManifest,
    CutoverReleaseState,
    CutoverSlice,
    CutoverSliceApproval,
    CutoverSlicePreview,
    CutoverSliceStatus,
)
from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE
from coeus.persistence.cutover_activation_evidence import digest, preview_digest, record_evidence
from coeus.persistence.cutover_activation_execution import (
    candidate_is_eligible,
    finish_activation,
    prepare_activation,
)
from coeus.persistence.cutover_activation_guards import (
    approval_bindings,
    lock_preview,
    lock_release,
    require_execution_people,
    require_manifest_evidence,
)
from coeus.persistence.cutover_activation_rows import read_release_state
from coeus.persistence.cutover_activation_snapshots import (
    capture_snapshot,
    lock_active_administrator,
    require_current_schema,
    require_no_blocking_drift,
)
from coeus.persistence.cutover_activation_sql import (
    INSERT_APPROVAL,
    LOCK_EXECUTION,
    MARK_APPROVED,
    SELECT_APPROVALS,
    UPSERT_PREVIEW,
)

_PREVIEW_TTL = timedelta(minutes=15)


class PostgresCutoverActivationStore(CutoverActivationStore):
    """Persist one immutable release candidate and activate its bounded slices."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def state(self) -> CutoverReleaseState:
        with self._engine.connect() as connection:
            state = read_release_state(connection)
            if state.manifest is None or state.candidate_hash is None:
                return state
            eligible = candidate_is_eligible(
                connection,
                state.candidate_hash,
                state.manifest.source_revision,
                ROUTING_RELATIONAL_CAPACITY_RELEASE,
            )
            return replace(state, eligible=eligible)

    def preview(
        self,
        slice: CutoverSlice,
        manifest: CutoverManifest,
        actor_user_id: UUID,
        occurred_at: datetime,
    ) -> CutoverSlicePreview:
        with self._transaction() as connection:
            lock_active_administrator(connection, actor_user_id)
            require_current_schema(connection)
            require_no_blocking_drift(connection)
            snapshot = capture_snapshot(connection, slice)
            require_manifest_evidence(manifest, slice, snapshot.source_hash, snapshot.parity)
            lock_release(connection, manifest, actor_user_id, occurred_at)
            existing = connection.execute(
                text(
                    "SELECT status FROM organisation_cutover_slice_state "
                    "WHERE candidate_hash=:candidate AND slice=:slice FOR UPDATE"
                ),
                {"candidate": manifest.candidate_hash, "slice": slice.value},
            ).scalar_one_or_none()
            if existing is not None:
                detail = (
                    "an active cutover slice is forward-only"
                    if existing == CutoverSliceStatus.ACTIVE.value
                    else "the exact candidate slice already has an immutable preview"
                )
                raise ValueError(detail)
            preview_hash = preview_digest(manifest, slice, snapshot, actor_user_id, occurred_at)
            expires_at = occurred_at + _PREVIEW_TTL
            connection.execute(
                text(UPSERT_PREVIEW),
                {
                    "candidate": manifest.candidate_hash,
                    "slice": slice.value,
                    "preview": preview_hash,
                    "actor": actor_user_id,
                    "at": occurred_at,
                    "expires": expires_at,
                    "source": snapshot.source_hash,
                    "target": snapshot.target_hash,
                    "visibility": snapshot.visibility_hash,
                },
            )
            record_evidence(
                connection,
                candidate_hash=manifest.candidate_hash,
                slice=slice,
                kind="preview",
                evidence_hash=preview_hash,
                actor=actor_user_id,
                occurred_at=occurred_at,
                payload={"expires_at": expires_at.isoformat()},
                snapshot=snapshot,
            )
            return CutoverSlicePreview(
                slice, manifest.candidate_hash, preview_hash, actor_user_id, expires_at
            )

    def approve(
        self,
        slice: CutoverSlice,
        candidate_hash: str,
        preview_hash: str,
        approval_role: CutoverApprovalRole,
        actor_user_id: UUID,
        occurred_at: datetime,
    ) -> CutoverSliceApproval:
        with self._transaction() as connection:
            lock_active_administrator(connection, actor_user_id)
            row = lock_preview(connection, slice, candidate_hash, preview_hash, occurred_at)
            if actor_user_id == row.proposed_by_user_id:
                raise PermissionError("a proposer cannot approve their own candidate")
            prior = tuple(
                connection.execute(
                    text(
                        "SELECT approved_by_user_id,approval_role "
                        "FROM organisation_cutover_approvals "
                        "WHERE candidate_hash=:candidate AND slice=:slice FOR SHARE"
                    ),
                    {"candidate": candidate_hash, "slice": slice.value},
                ).mappings()
            )
            prior_actors = {item["approved_by_user_id"] for item in prior}
            if actor_user_id in prior_actors:
                raise PermissionError("cutover approval roles require distinct people")
            if approval_role.value in {item["approval_role"] for item in prior}:
                raise ValueError("the approval role already has immutable evidence")
            approval_id = uuid4()
            connection.execute(
                text(INSERT_APPROVAL),
                {
                    "id": approval_id,
                    "candidate": candidate_hash,
                    "slice": slice.value,
                    "role": approval_role.value,
                    "preview": preview_hash,
                    "actor": actor_user_id,
                    "at": occurred_at,
                },
            )
            roles = set(
                connection.execute(
                    text(
                        "SELECT approval_role FROM organisation_cutover_approvals "
                        "WHERE candidate_hash=:candidate AND slice=:slice"
                    ),
                    {"candidate": candidate_hash, "slice": slice.value},
                ).scalars()
            )
            if roles == {item.value for item in CutoverApprovalRole}:
                connection.execute(
                    text(MARK_APPROVED),
                    approval_bindings(candidate_hash, slice, occurred_at),
                )
            evidence_hash = digest(
                {"approval_id": approval_id, "role": approval_role.value, "preview": preview_hash}
            )
            record_evidence(
                connection,
                candidate_hash=candidate_hash,
                slice=slice,
                kind="approval",
                evidence_hash=evidence_hash,
                actor=actor_user_id,
                occurred_at=occurred_at,
                payload={"approval_id": str(approval_id), "role": approval_role.value},
            )
            return CutoverSliceApproval(
                approval_id,
                slice,
                candidate_hash,
                preview_hash,
                approval_role,
                actor_user_id,
                occurred_at,
            )

    def execute(
        self,
        slice: CutoverSlice,
        candidate_hash: str,
        approval_ids: tuple[UUID, ...],
        actor_user_id: UUID,
        occurred_at: datetime,
    ) -> CutoverExecutionResult:
        with self._transaction() as connection:
            lock_active_administrator(connection, actor_user_id)
            state = (
                connection.execute(
                    text(LOCK_EXECUTION), {"candidate": candidate_hash, "slice": slice.value}
                )
                .mappings()
                .one_or_none()
            )
            if (
                state is None
                or state["status"] != CutoverSliceStatus.APPROVED.value
                or state["preview_expires_at"] <= occurred_at
            ):
                raise ValueError("the exact candidate slice is not approved")
            if len(approval_ids) != 2 or len(set(approval_ids)) != 2:
                raise ValueError("both distinct approval records are required")
            approvals = tuple(
                connection.execute(
                    text(SELECT_APPROVALS),
                    {
                        "candidate": candidate_hash,
                        "slice": slice.value,
                        "first": approval_ids[0],
                        "second": approval_ids[1],
                    },
                ).mappings()
            )
            require_execution_people(approvals, state["proposed_by_user_id"], actor_user_id)
            if {row["preview_hash"] for row in approvals} != {state["preview_hash"]}:
                raise ValueError("approval evidence does not match the exact preview")
            snapshot = capture_snapshot(connection, slice)
            if not snapshot.parity or snapshot.source_hash != state["source_snapshot_hash"]:
                raise ValueError("source or target visibility changed after approval")
            require_current_schema(connection)
            require_no_blocking_drift(connection)
            checkpoint, lease = prepare_activation(
                connection,
                slice,
                candidate_hash,
                actor_user_id,
                occurred_at,
                snapshot,
            )
        with self._transaction() as connection:
            lock_active_administrator(connection, actor_user_id)
            require_current_schema(connection)
            require_no_blocking_drift(connection)
            finish_activation(
                connection,
                slice,
                candidate_hash,
                actor_user_id,
                occurred_at,
                snapshot,
                checkpoint,
                lease,
            )
            eligible = candidate_is_eligible(connection, candidate_hash, None, None)
            return CutoverExecutionResult(
                candidate_hash, slice, CutoverSliceStatus.ACTIVE, eligible
            )

    def active_candidate_is_eligible(
        self, candidate_hash: str, source_revision: str, routing_release: str
    ) -> bool:
        with self._engine.connect() as connection:
            return candidate_is_eligible(
                connection, candidate_hash, source_revision, routing_release
            )

    def _transaction(self) -> AbstractContextManager[Connection]:
        return self._engine.execution_options(isolation_level="SERIALIZABLE").begin()
