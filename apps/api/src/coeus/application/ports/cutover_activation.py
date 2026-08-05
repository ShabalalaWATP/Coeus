"""Persistence boundary for exact-candidate organisation cutover."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverExecutionResult,
    CutoverManifest,
    CutoverReleaseState,
    CutoverSlice,
    CutoverSliceApproval,
    CutoverSlicePreview,
)


class CutoverActivationStore(Protocol):
    def state(self) -> CutoverReleaseState: ...

    def preview(
        self,
        slice: CutoverSlice,
        manifest: CutoverManifest,
        actor_user_id: UUID,
        occurred_at: datetime,
    ) -> CutoverSlicePreview: ...

    def approve(
        self,
        slice: CutoverSlice,
        candidate_hash: str,
        preview_hash: str,
        approval_role: CutoverApprovalRole,
        actor_user_id: UUID,
        occurred_at: datetime,
    ) -> CutoverSliceApproval: ...

    def execute(
        self,
        slice: CutoverSlice,
        candidate_hash: str,
        approval_ids: tuple[UUID, ...],
        actor_user_id: UUID,
        occurred_at: datetime,
    ) -> CutoverExecutionResult: ...

    def active_candidate_is_eligible(
        self, candidate_hash: str, source_revision: str, routing_release: str
    ) -> bool: ...
