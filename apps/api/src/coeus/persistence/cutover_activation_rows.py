"""Map immutable cutover PostgreSQL rows to domain release state."""

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverManifest,
    CutoverReleaseState,
    CutoverSlice,
    CutoverSliceApproval,
    CutoverSliceState,
    CutoverSliceStatus,
)
from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE


def read_release_state(connection: Connection) -> CutoverReleaseState:
    release = connection.execute(text(_RELEASE)).mappings().one_or_none()
    if release is None:
        return CutoverReleaseState(
            None,
            None,
            tuple(
                CutoverSliceState(item, CutoverSliceStatus.NOT_PREVIEWED) for item in CutoverSlice
            ),
            False,
        )
    candidate = release["candidate_hash"]
    manifest = CutoverManifest(*(release[name] for name in _MANIFEST_FIELDS))
    rows = {
        CutoverSlice(row["slice"]): row
        for row in connection.execute(text(_SLICES), {"candidate": candidate}).mappings()
    }
    approvals: dict[CutoverSlice, list[CutoverSliceApproval]] = {item: [] for item in CutoverSlice}
    for row in connection.execute(text(_APPROVALS), {"candidate": candidate}).mappings():
        slice = CutoverSlice(row["slice"])
        approvals[slice].append(
            CutoverSliceApproval(
                row["approval_id"],
                slice,
                candidate,
                row["preview_hash"],
                CutoverApprovalRole(row["approval_role"]),
                row["approved_by_user_id"],
                row["approved_at"],
            )
        )
    states = tuple(_state(item, rows.get(item), approvals[item]) for item in CutoverSlice)
    fences = connection.execute(text(_FENCES), {"candidate": candidate}).scalar_one()
    eligible = (
        all(state.status is CutoverSliceStatus.ACTIVE for state in states)
        and int(fences) == len(CutoverSlice)
        and manifest.routing_evaluation_release == ROUTING_RELATIONAL_CAPACITY_RELEASE
    )
    return CutoverReleaseState(candidate, manifest, states, eligible)


def _state(
    slice: CutoverSlice,
    row: RowMapping | None,
    approvals: list[CutoverSliceApproval],
) -> CutoverSliceState:
    if row is None:
        return CutoverSliceState(slice, CutoverSliceStatus.NOT_PREVIEWED)
    return CutoverSliceState(
        slice,
        CutoverSliceStatus(row["status"]),
        row["preview_hash"],
        row["proposed_by_user_id"],
        tuple(approvals),
        row["activated_by_user_id"],
        row["activated_at"],
    )


_MANIFEST_FIELDS = (
    "source_revision",
    "schema_head",
    "organisation_parity_hash",
    "calendar_parity_hash",
    "task_capacity_parity_hash",
    "routing_evaluation_release",
    "routing_evaluation_hash",
    "protected_checks_reference",
    "protected_checks_hash",
    "browser_evidence_hash",
    "security_review_reference",
    "security_review_hash",
    "backup_restore_hash",
)
_RELEASE = """SELECT manifest.* FROM organisation_cutover_release release
JOIN organisation_cutover_manifests manifest USING (candidate_hash)
WHERE release.singleton"""
_SLICES = """SELECT * FROM organisation_cutover_slice_state
WHERE candidate_hash=:candidate ORDER BY slice"""
_APPROVALS = """SELECT * FROM organisation_cutover_approvals
WHERE candidate_hash=:candidate ORDER BY approved_at,approval_id"""
_FENCES = """SELECT count(*) FROM organisation_cutover_writer_fences
WHERE candidate_hash=:candidate AND state='target_authoritative'"""
