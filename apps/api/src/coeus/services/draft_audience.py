"""Central draft-audience decisions shared by Store and workflow reads."""

from coeus.application.ports.draft_audience import DraftAudienceProjection
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.draft_audience import DraftAudienceReason
from coeus.domain.store import StoreProduct


class RoleAwareDraftAudiencePolicy:
    """Authorise only a supplied object relationship or an explicit privileged role."""

    def reason_for_store_read(
        self, actor: UserAccount, product: StoreProduct
    ) -> DraftAudienceReason | None:
        if product.created_by_user_id == actor.user_id:
            return DraftAudienceReason.CREATOR
        if RoleName.ADMINISTRATOR in actor.roles:
            return DraftAudienceReason.ADMINISTRATOR
        if RoleName.INTELLIGENCE_STORE_MANAGER in actor.roles:
            return DraftAudienceReason.STORE_MANAGER
        return None

    def permits(
        self,
        actor: UserAccount,
        product: StoreProduct,
        reason: DraftAudienceReason | None,
        *,
        require_projection: bool = False,
    ) -> bool:
        if reason is None:
            return False
        if reason == DraftAudienceReason.ADMINISTRATOR:
            return RoleName.ADMINISTRATOR in actor.roles
        if reason == DraftAudienceReason.STORE_MANAGER:
            return RoleName.INTELLIGENCE_STORE_MANAGER in actor.roles
        relationship = reason in {
            DraftAudienceReason.CREATOR,
            DraftAudienceReason.ASSIGNED_ANALYST,
            DraftAudienceReason.RESPONSIBLE_MANAGER,
            DraftAudienceReason.QUALITY_CONTROL,
        }
        if not relationship:
            return False
        if require_projection and self._projection is not None:
            return self._projection.contains(product.product_id, actor.user_id, reason)
        return True

    def __init__(self, projection: DraftAudienceProjection | None = None) -> None:
        self._projection = projection
