from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.draft_audience import DraftAudienceReason
from coeus.services.draft_audience import RoleAwareDraftAudiencePolicy
from store_projection_helpers import seed_product


def _user(*roles: RoleName) -> UserAccount:
    return UserAccount(
        user_id=uuid4(),
        username=f"{uuid4()}@example.test",
        display_name="Synthetic audience user",
        roles=frozenset(roles),
        permissions=frozenset(),
        password_hash="synthetic-hash",  # noqa: S106
        is_active=True,
        clearance_level=3,
    )


@pytest.mark.parametrize(
    "reason",
    (
        DraftAudienceReason.CREATOR,
        DraftAudienceReason.ASSIGNED_ANALYST,
        DraftAudienceReason.RESPONSIBLE_MANAGER,
        DraftAudienceReason.QUALITY_CONTROL,
    ),
)
def test_object_relationship_reasons_are_explicitly_permitted(
    reason: DraftAudienceReason,
) -> None:
    assert RoleAwareDraftAudiencePolicy().permits(_user(), reason)


def test_privileged_reasons_require_the_corresponding_current_role() -> None:
    policy = RoleAwareDraftAudiencePolicy()

    assert policy.permits(_user(RoleName.ADMINISTRATOR), DraftAudienceReason.ADMINISTRATOR)
    assert policy.permits(
        _user(RoleName.INTELLIGENCE_STORE_MANAGER), DraftAudienceReason.STORE_MANAGER
    )
    assert not policy.permits(_user(), DraftAudienceReason.ADMINISTRATOR)
    assert not policy.permits(_user(), None)


def test_store_read_reason_is_creator_or_current_privileged_role_only() -> None:
    policy = RoleAwareDraftAudiencePolicy()
    creator = _user()
    product = replace(seed_product(), created_by_user_id=creator.user_id)

    assert policy.reason_for_store_read(creator, product) == DraftAudienceReason.CREATOR
    assert (
        policy.reason_for_store_read(_user(RoleName.ADMINISTRATOR), product)
        == DraftAudienceReason.ADMINISTRATOR
    )
    assert policy.reason_for_store_read(_user(), product) is None
