from typing import Protocol
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.draft_audience import DraftAudienceReason
from coeus.domain.store import AssetAccessGrant, StoreProduct, StoreVisibilityScope
from coeus.repositories.store import StoreRepository
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.audit import AuditLog


class StoreReadPolicy(Protocol):
    def can_read(self, user: UserAccount, product: StoreProduct) -> bool:
        pass

    def visibility_scope(self, user: UserAccount) -> StoreVisibilityScope:
        pass

    def can_read_for_workflow(
        self,
        user: UserAccount,
        product: StoreProduct,
        reason: DraftAudienceReason,
        require_projection: bool = False,
    ) -> bool:
        pass


class StoreDetailService:
    def __init__(
        self,
        repository: StoreRepository,
        policy: StoreReadPolicy,
        audit_log: AuditLog,
    ) -> None:
        self._repository = repository
        self._policy = policy
        self._audit_log = audit_log

    def get_visible_product(self, actor: UserAccount, product_id: UUID) -> StoreProduct:
        product = self._repository.get_visible_product(
            product_id, self._policy.visibility_scope(actor)
        )
        if product is None or not self.can_read_product(actor, product):
            raise AppError(404, "product_not_found", "Product was not found.")
        return product

    def visible_product_ids(
        self, actor: UserAccount, product_ids: frozenset[UUID]
    ) -> frozenset[UUID]:
        products = self._repository.get_visible_products(
            product_ids, self._policy.visibility_scope(actor)
        )
        return frozenset(
            product.product_id for product in products if self.can_read_product(actor, product)
        )

    def can_read_product(self, actor: UserAccount, product: StoreProduct) -> bool:
        return self._policy.can_read(actor, product)

    def get_workflow_visible_product(
        self,
        actor: UserAccount,
        product_id: UUID,
        reason: DraftAudienceReason,
        *,
        require_projection: bool = False,
    ) -> StoreProduct:
        """Read a product in an already-authorised assigned-workflow context."""
        product = self._repository.get_product(product_id)
        if product is None or not self._policy.can_read_for_workflow(
            actor, product, reason, require_projection
        ):
            raise AppError(404, "product_not_found", "Product was not found.")
        return product

    def get_break_glass_product(
        self, actor: UserAccount, product_id: UUID, reason: str
    ) -> StoreProduct:
        product = self.get_restricted_product(actor, product_id)
        self._audit_log.record(
            "product_break_glass_accessed",
            str(actor.user_id),
            {"product_id": str(product_id), "reason": reason.strip()},
        )
        return product

    def get_restricted_product(self, actor: UserAccount, product_id: UUID) -> StoreProduct:
        if Permission.PRODUCT_READ_RESTRICTED not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        product = self._repository.get_product(product_id)
        if product is None:
            raise AppError(404, "product_not_found", "Product was not found.")
        return product


class StoreAssetService:
    def __init__(
        self,
        details: StoreDetailService,
        tokens: AssetTokenService,
        audit_log: AuditLog,
    ) -> None:
        self._details = details
        self._tokens = tokens
        self._audit_log = audit_log

    def grant_access(
        self, actor: UserAccount, product_id: UUID, asset_id: UUID
    ) -> AssetAccessGrant:
        if Permission.PRODUCT_DOWNLOAD not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        product = self._details.get_visible_product(actor, product_id)
        for asset in product.assets:
            if asset.asset_id == asset_id:
                return AssetAccessGrant(
                    asset=asset,
                    download_token=self._tokens.issue(actor, product_id, asset_id),
                    expires_in_seconds=900,
                )
        raise AppError(404, "asset_not_found", "Asset was not found.")

    def grant_break_glass_access(
        self,
        actor: UserAccount,
        product_id: UUID,
        asset_id: UUID,
        reason: str,
    ) -> AssetAccessGrant:
        product = self._details.get_restricted_product(actor, product_id)
        for asset in product.assets:
            if asset.asset_id == asset_id:
                self._audit_log.record(
                    "product_asset_break_glass_accessed",
                    str(actor.user_id),
                    {
                        "product_id": str(product_id),
                        "asset_id": str(asset_id),
                        "reason": reason.strip(),
                    },
                )
                return AssetAccessGrant(
                    asset=asset,
                    download_token=self._tokens.issue(
                        actor, product_id, asset_id, break_glass=True
                    ),
                    expires_in_seconds=900,
                )
        raise AppError(404, "asset_not_found", "Asset was not found.")
