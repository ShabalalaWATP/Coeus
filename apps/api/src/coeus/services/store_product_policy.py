from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.store import StoreProduct, StoreVisibilityScope
from coeus.repositories.access import AccessRepository


class StoreProductAccessPolicy:
    def __init__(self, access_repository: AccessRepository) -> None:
        self._access_repository = access_repository

    def can_read(self, user: UserAccount, product: StoreProduct) -> bool:
        metadata = product.metadata
        if Permission.PRODUCT_READ not in user.permissions or not user.is_active:
            return False
        if metadata.status == ProductStatus.ARCHIVED:
            return False
        if user.clearance_level < metadata.classification_level:
            return False
        if (
            metadata.status == ProductStatus.DRAFT
            and Permission.PRODUCT_MANAGE_ASSETS not in user.permissions
        ):
            return False
        user_acg_ids = self._access_repository.active_acg_ids_for_user(user.user_id)
        return bool(user_acg_ids.intersection(metadata.acg_ids))

    def visibility_scope(self, user: UserAccount) -> StoreVisibilityScope:
        return StoreVisibilityScope(
            acg_ids=self._access_repository.active_acg_ids_for_user(user.user_id),
            clearance_level=user.clearance_level,
            include_drafts=Permission.PRODUCT_MANAGE_ASSETS in user.permissions,
        )
