"""Port for persisted draft-product audience relationships."""

from typing import Protocol
from uuid import UUID

from coeus.domain.auth import UserAccount
from coeus.domain.draft_audience import DraftAudienceReason
from coeus.domain.store import StoreProduct


class DraftAudienceProjection(Protocol):
    def reasons_for(
        self, product_id: UUID, principal_id: UUID
    ) -> tuple[DraftAudienceReason, ...]: ...

    def contains(
        self, product_id: UUID, principal_id: UUID, reason: DraftAudienceReason
    ) -> bool: ...


class DraftAudiencePolicy(Protocol):
    """Object-specific authorisation for unpublished Store products."""

    def reason_for_store_read(
        self, actor: UserAccount, product: StoreProduct
    ) -> DraftAudienceReason | None: ...

    def permits(
        self,
        actor: UserAccount,
        product: StoreProduct,
        reason: DraftAudienceReason | None,
        *,
        require_projection: bool = False,
    ) -> bool: ...
