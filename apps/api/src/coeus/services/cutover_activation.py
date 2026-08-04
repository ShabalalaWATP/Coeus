"""Release-gated state machine for activating organisation bounded contexts."""

from datetime import UTC, datetime
from uuid import UUID

from coeus.application.ports.cutover_activation import CutoverActivationStore
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverExecutionResult,
    CutoverManifest,
    CutoverReleaseState,
    CutoverSlice,
    CutoverSliceApproval,
    CutoverSlicePreview,
    validate_candidate_hash,
)
from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE


class CutoverActivationDenied(Exception):
    """The requested cutover transition is not safe or authorised."""


class CutoverActivationConflict(Exception):
    """The exact candidate or its current evidence changed."""


class CutoverActivationService:
    def __init__(self, store: CutoverActivationStore) -> None:
        self._store = store

    def state(self) -> CutoverReleaseState:
        return self._store.state()

    def preview(
        self, slice: CutoverSlice, manifest: CutoverManifest, actor: UserAccount
    ) -> CutoverSlicePreview:
        self._require_active_administrator(actor)
        try:
            return self._store.preview(slice, manifest, actor.user_id, datetime.now(UTC))
        except ValueError as exc:
            raise CutoverActivationConflict(str(exc)) from exc

    def approve(
        self,
        slice: CutoverSlice,
        candidate_hash: str,
        preview_hash: str,
        approval_role: CutoverApprovalRole,
        actor: UserAccount,
        *,
        reauthenticated: bool,
    ) -> CutoverSliceApproval:
        self._require_sensitive_actor(actor, reauthenticated)
        self._validate_hashes(candidate_hash, preview_hash)
        try:
            return self._store.approve(
                slice,
                candidate_hash,
                preview_hash,
                approval_role,
                actor.user_id,
                datetime.now(UTC),
            )
        except PermissionError as exc:
            raise CutoverActivationDenied("an independent approver is required") from exc
        except ValueError as exc:
            raise CutoverActivationConflict(str(exc)) from exc

    def execute(
        self,
        slice: CutoverSlice,
        candidate_hash: str,
        approval_ids: tuple[UUID, ...],
        actor: UserAccount,
        *,
        reauthenticated: bool,
    ) -> CutoverExecutionResult:
        self._require_sensitive_actor(actor, reauthenticated)
        validate_candidate_hash(candidate_hash)
        if len(approval_ids) != 2 or len(set(approval_ids)) != 2:
            raise CutoverActivationDenied("both distinct cutover approvals are required")
        try:
            return self._store.execute(
                slice, candidate_hash, approval_ids, actor.user_id, datetime.now(UTC)
            )
        except PermissionError as exc:
            raise CutoverActivationDenied(
                "the proposer, approver and activation executor must be distinct"
            ) from exc
        except ValueError as exc:
            raise CutoverActivationConflict(str(exc)) from exc

    def assert_active_composition_eligible(
        self, candidate_hash: str | None, source_revision: str | None
    ) -> None:
        if candidate_hash is None or source_revision is None:
            raise CutoverActivationDenied("active cutover candidate is not configured")
        validate_candidate_hash(candidate_hash)
        if not self._store.active_candidate_is_eligible(
            candidate_hash, source_revision, ROUTING_RELATIONAL_CAPACITY_RELEASE
        ):
            raise CutoverActivationDenied("the configured active cutover candidate is not eligible")

    @staticmethod
    def _require_active_administrator(actor: UserAccount) -> None:
        if (
            not actor.is_active
            or RoleName.ADMINISTRATOR not in actor.roles
            or Permission.SYSTEM_CONFIGURE not in actor.permissions
        ):
            raise CutoverActivationDenied("an active platform administrator is required")

    @classmethod
    def _require_sensitive_actor(cls, actor: UserAccount, reauthenticated: bool) -> None:
        cls._require_active_administrator(actor)
        if not reauthenticated:
            raise CutoverActivationDenied("recent reauthentication is required")

    @staticmethod
    def _validate_hashes(candidate_hash: str, preview_hash: str) -> None:
        validate_candidate_hash(candidate_hash)
        validate_candidate_hash(preview_hash)
