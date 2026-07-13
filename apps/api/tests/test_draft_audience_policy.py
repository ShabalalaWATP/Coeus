from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

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


def test_explicit_workflow_relationship_reasons_support_local_mode() -> None:
    policy = RoleAwareDraftAudiencePolicy()
    actor = _user()
    product = seed_product()

    assert policy.permits(actor, product, DraftAudienceReason.CREATOR)
    for reason in (
        DraftAudienceReason.ASSIGNED_ANALYST,
        DraftAudienceReason.RESPONSIBLE_MANAGER,
        DraftAudienceReason.QUALITY_CONTROL,
    ):
        assert policy.permits(actor, product, reason)


def test_privileged_reasons_require_the_corresponding_current_role() -> None:
    policy = RoleAwareDraftAudiencePolicy()

    product = seed_product()
    assert policy.permits(_user(RoleName.ADMINISTRATOR), product, DraftAudienceReason.ADMINISTRATOR)
    assert policy.permits(
        _user(RoleName.INTELLIGENCE_STORE_MANAGER),
        product,
        DraftAudienceReason.STORE_MANAGER,
    )
    assert not policy.permits(_user(), product, DraftAudienceReason.ADMINISTRATOR)
    assert not policy.permits(_user(), product, None)


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


def test_projected_relationship_drives_store_reason_and_permission() -> None:
    class Projection:
        def reasons_for(
            self, product_id: UUID, principal_id: UUID
        ) -> tuple[DraftAudienceReason, ...]:
            return (DraftAudienceReason.ASSIGNED_ANALYST,)

        def contains(
            self, product_id: UUID, principal_id: UUID, reason: DraftAudienceReason
        ) -> bool:
            return reason == DraftAudienceReason.ASSIGNED_ANALYST

    actor = _user()
    product = seed_product()
    policy = RoleAwareDraftAudiencePolicy(Projection())

    assert policy.reason_for_store_read(actor, product) == DraftAudienceReason.ASSIGNED_ANALYST
    assert policy.permits(
        actor,
        product,
        DraftAudienceReason.ASSIGNED_ANALYST,
        require_projection=True,
    )


def test_projected_reason_order_and_unknown_reasons_fail_closed() -> None:
    class Projection:
        def __init__(self, reasons: tuple[DraftAudienceReason, ...]) -> None:
            self._reasons = reasons

        def reasons_for(
            self, _product_id: UUID, _principal_id: UUID
        ) -> tuple[DraftAudienceReason, ...]:
            return self._reasons

        def contains(
            self, _product_id: UUID, _principal_id: UUID, reason: DraftAudienceReason
        ) -> bool:
            return reason in self._reasons

    actor = _user()
    product = seed_product()

    assert (
        RoleAwareDraftAudiencePolicy(
            Projection((DraftAudienceReason.RESPONSIBLE_MANAGER,))
        ).reason_for_store_read(actor, product)
        == DraftAudienceReason.RESPONSIBLE_MANAGER
    )
    assert (
        RoleAwareDraftAudiencePolicy(Projection(())).reason_for_store_read(actor, product) is None
    )
    assert not RoleAwareDraftAudiencePolicy().permits(
        actor, product, cast(DraftAudienceReason, "unsupported")
    )
