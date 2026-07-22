"""Result mapping and local checks for protected product submissions."""

from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.submission_authority import (
    SubmissionCommitResult,
    submission_authority_result,
)
from coeus.persistence.codec import decode_value
from coeus.persistence.state_store import StateStore


def local_submission_authority(
    state_store: StateStore,
    actor_user_id: UUID,
    required_acg_ids: frozenset[UUID],
) -> SubmissionCommitResult:
    user_payload = state_store.load("users") or {}
    access_payload = state_store.load("access") or {}
    users = tuple(decode_value(item) for item in user_payload.get("users", []))
    acgs = tuple(decode_value(item) for item in access_payload.get("acgs", []))
    memberships = tuple(decode_value(item) for item in access_payload.get("memberships", []))
    return submission_authority_result(users, acgs, memberships, actor_user_id, required_acg_ids)


def raise_submission_conflict(result: SubmissionCommitResult, ticket_changed: AppError) -> None:
    if result is SubmissionCommitResult.COMMITTED:
        return
    if result is SubmissionCommitResult.TICKET_CHANGED:
        raise ticket_changed
    if result is SubmissionCommitResult.ACG_INACTIVE:
        raise AppError(409, "product_acg_required", "Products must use active ACGs.")
    if result is SubmissionCommitResult.ACG_NOT_AUTHORISED:
        raise AppError(403, "acg_not_authorised", "User cannot assign that ACG.")
    raise AppError(403, "forbidden", "Permission denied.")
