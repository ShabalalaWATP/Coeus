"""Authorisation for the initial lifecycle state of existing Store products."""

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount


def require_product_creation_status(actor: UserAccount, status: ProductStatus) -> None:
    if Permission.PRODUCT_CREATE_EXISTING not in actor.permissions:
        raise AppError(403, "forbidden", "Permission denied.")
    if status not in {ProductStatus.DRAFT, ProductStatus.PUBLISHED}:
        raise AppError(409, "product_status_invalid", "Product status is not supported.")
    if status == ProductStatus.PUBLISHED and Permission.PRODUCT_PUBLISH not in actor.permissions:
        raise AppError(403, "forbidden", "Permission denied.")
