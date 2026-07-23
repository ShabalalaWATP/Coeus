"""Current-authority checks shared by Store asset redemption routes."""

from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.store import StoreAsset
from coeus.services.asset_tokens import AssetTokenClaims
from coeus.services.store_access import StoreDetailService


def redeemable_asset(
    claims: AssetTokenClaims,
    actor: UserAccount,
    product_id: UUID,
    asset_id: UUID,
    details: StoreDetailService,
) -> StoreAsset:
    """Resolve a bound asset after repeating its mutable authorisation policy."""
    if (
        claims.user_id != actor.user_id
        or claims.product_id != product_id
        or claims.asset_id != asset_id
    ):
        raise AppError(403, "asset_token_invalid", "Asset token is invalid.")

    if claims.break_glass:
        product = details.get_restricted_product(actor, product_id)
    else:
        # Preserve the hidden-object 404 before disclosing action authority.
        product = details.get_visible_product(actor, product_id)
        if Permission.PRODUCT_DOWNLOAD not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    asset = next((item for item in product.assets if item.asset_id == asset_id), None)
    if asset is None:
        raise AppError(404, "asset_not_found", "Asset was not found.")
    return asset
