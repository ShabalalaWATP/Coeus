"""Decision-table coverage for product-submission authority."""

from dataclasses import replace
from uuid import uuid4

from coeus.core.permissions import Permission
from coeus.domain.access import AccessControlGroup, AccessControlGroupMembership
from coeus.domain.auth import UserAccount
from coeus.domain.submission_authority import (
    SubmissionCommitResult,
    submission_authority_result,
)


def test_submission_authority_requires_current_actor_active_acg_and_membership() -> None:
    actor = _actor({Permission.ANALYST_SUBMIT_PRODUCT})
    acg = _acg(active=True)
    membership = AccessControlGroupMembership(acg.acg_id, actor.user_id)
    required = frozenset({acg.acg_id})

    assert (
        submission_authority_result((actor,), (acg,), (membership,), actor.user_id, required)
        is SubmissionCommitResult.COMMITTED
    )
    assert submission_authority_result((), (acg,), (membership,), actor.user_id, required) is (
        SubmissionCommitResult.ACTOR_REVOKED
    )
    assert (
        submission_authority_result(
            (replace(actor, is_active=False),), (acg,), (membership,), actor.user_id, required
        )
        is SubmissionCommitResult.ACTOR_REVOKED
    )
    assert (
        submission_authority_result(
            (actor,), (replace(acg, is_active=False),), (membership,), actor.user_id, required
        )
        is SubmissionCommitResult.ACG_INACTIVE
    )
    assert submission_authority_result((actor,), (acg,), (), actor.user_id, required) is (
        SubmissionCommitResult.ACG_NOT_AUTHORISED
    )


def test_restricted_product_reader_can_assign_any_active_acg() -> None:
    actor = _actor({Permission.ANALYST_SUBMIT_PRODUCT, Permission.PRODUCT_READ_RESTRICTED})
    acg = _acg(active=True)

    assert (
        submission_authority_result((actor,), (acg,), (), actor.user_id, frozenset({acg.acg_id}))
        is SubmissionCommitResult.COMMITTED
    )


def _actor(permissions: set[Permission]) -> UserAccount:
    return UserAccount(
        user_id=uuid4(),
        username="synthetic-analyst@example.test",
        display_name="Synthetic Analyst",
        roles=frozenset(),
        permissions=frozenset(permissions),
        password_hash="synthetic-test-value",  # noqa: S106
        is_active=True,
        clearance_level=3,
    )


def _acg(*, active: bool) -> AccessControlGroup:
    return AccessControlGroup(
        acg_id=uuid4(),
        code="ACG-SYNTHETIC",
        name="Synthetic",
        description="Synthetic test ACG.",
        owner_user_id=None,
        is_active=active,
    )
