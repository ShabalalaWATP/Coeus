from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.store import StoreProduct, StoreVisibilityScope
from coeus.repositories.access import AccessRepository


class StoreProductAccessPolicy:
    def __init__(self, access_repository: AccessRepository) -> None:
        self._access_repository = access_repository

    def can_read(self, user: UserAccount, product: StoreProduct) -> bool:
        if not self.can_read_for_workflow(user, product):
            return False
        metadata = product.metadata
        return not (
            metadata.status == ProductStatus.DRAFT
            and product.created_by_user_id != user.user_id
            and not _can_read_all_drafts(user)
        )

    def can_read_for_workflow(self, user: UserAccount, product: StoreProduct) -> bool:
        """Apply all read controls except the draft audience already established by a task."""
        metadata = product.metadata
        if Permission.PRODUCT_READ not in user.permissions or not user.is_active:
            return False
        if metadata.status == ProductStatus.ARCHIVED:
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
        )


def _can_read_all_drafts(user: UserAccount) -> bool:
    return bool(
        user.roles.intersection({RoleName.ADMINISTRATOR, RoleName.INTELLIGENCE_STORE_MANAGER})
    )
