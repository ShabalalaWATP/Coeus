"""Pure authority decisions for committing protected product submissions."""

from enum import StrEnum
from uuid import UUID

from coeus.core.permissions import Permission
from coeus.domain.access import AccessControlGroup, AccessControlGroupMembership
from coeus.domain.auth import UserAccount


class SubmissionCommitResult(StrEnum):
    COMMITTED = "committed"
    TICKET_CHANGED = "ticket_changed"
    ACTOR_REVOKED = "actor_revoked"
    ACG_INACTIVE = "acg_inactive"
    ACG_NOT_AUTHORISED = "acg_not_authorised"


def submission_authority_result(
    users: tuple[UserAccount, ...],
    acgs: tuple[AccessControlGroup, ...],
    memberships: tuple[AccessControlGroupMembership, ...],
    actor_id: UUID,
    required_acg_ids: frozenset[UUID],
) -> SubmissionCommitResult:
    actor = next((user for user in users if user.user_id == actor_id), None)
    if (
        actor is None
        or not actor.is_active
        or Permission.ANALYST_SUBMIT_PRODUCT not in actor.permissions
    ):
        return SubmissionCommitResult.ACTOR_REVOKED
    active_acg_ids = frozenset(acg.acg_id for acg in acgs if acg.is_active)
    if not required_acg_ids.issubset(active_acg_ids):
        return SubmissionCommitResult.ACG_INACTIVE
    if Permission.PRODUCT_READ_RESTRICTED in actor.permissions:
        return SubmissionCommitResult.COMMITTED
    actor_acg_ids = frozenset(
        membership.acg_id for membership in memberships if membership.user_id == actor_id
    )
    if not required_acg_ids.issubset(actor_acg_ids):
        return SubmissionCommitResult.ACG_NOT_AUTHORISED
    return SubmissionCommitResult.COMMITTED
