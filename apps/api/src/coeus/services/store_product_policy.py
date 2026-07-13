from coeus.application.ports.draft_audience import DraftAudiencePolicy
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.draft_audience import DraftAudienceReason
from coeus.domain.store import (
    StoreProduct,
    StoreVisibilityScope,
    normalise_synthetic_release_markers,
)
from coeus.repositories.access import AccessRepository
from coeus.services.draft_audience import RoleAwareDraftAudiencePolicy


class StoreProductAccessPolicy:
    def __init__(
        self,
        access_repository: AccessRepository,
        draft_audience: DraftAudiencePolicy | None = None,
    ) -> None:
        self._access_repository = access_repository
        self._draft_audience = draft_audience or RoleAwareDraftAudiencePolicy()

    def can_read(self, user: UserAccount, product: StoreProduct) -> bool:
        if not self._can_read_base(user, product):
            return False
        metadata = product.metadata
        return metadata.status != ProductStatus.DRAFT or self._draft_audience.permits(
            user, product, self._draft_audience.reason_for_store_read(user, product)
        )

    def can_read_for_workflow(
        self,
        user: UserAccount,
        product: StoreProduct,
        reason: DraftAudienceReason,
        require_projection: bool = False,
    ) -> bool:
        return self._can_read_base(user, product) and (
            product.metadata.status != ProductStatus.DRAFT
            or self._draft_audience.permits(
                user, product, reason, require_projection=require_projection
            )
        )

    def _can_read_base(self, user: UserAccount, product: StoreProduct) -> bool:
        metadata = product.metadata
        if Permission.PRODUCT_READ not in user.permissions or not user.is_active:
            return False
        if metadata.status == ProductStatus.ARCHIVED:
            return False
        try:
            normalise_synthetic_release_markers(metadata.releasability, metadata.handling_caveats)
        except ValueError:
            return False
        if user.clearance_level < metadata.classification_level:
            return False
        user_acg_ids = self._access_repository.active_acg_ids_for_user(user.user_id)
        return bool(user_acg_ids.intersection(metadata.acg_ids))

    def visibility_scope(self, user: UserAccount) -> StoreVisibilityScope:
        return StoreVisibilityScope(
            acg_ids=self._access_repository.active_acg_ids_for_user(user.user_id),
            clearance_level=user.clearance_level,
            include_drafts=_can_read_all_drafts(user),
            draft_creator_user_id=user.user_id,
            draft_principal_user_id=user.user_id,
        )


def _can_read_all_drafts(user: UserAccount) -> bool:
    return bool(
        user.roles.intersection({RoleName.ADMINISTRATOR, RoleName.INTELLIGENCE_STORE_MANAGER})
    )
