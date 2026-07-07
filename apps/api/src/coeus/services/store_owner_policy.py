from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount

MANAGED_OWNER_PERMISSIONS = {
    "rfa": Permission.RFA_ADD_PRODUCT,
    "collection": Permission.COLLECTION_ADD_PRODUCT,
}

OWNER_TEAM_LABELS = {
    "rfa": "RFA",
    "collection": "Collection",
}


def normalise_owner_team(owner_team: str) -> str:
    return OWNER_TEAM_LABELS[_owner_team_key(owner_team)]


def require_owner_permission(actor: UserAccount, owner_team: str) -> None:
    permission = MANAGED_OWNER_PERMISSIONS[_owner_team_key(owner_team)]
    is_store_manager = (
        Permission.PRODUCT_CREATE_EXISTING in actor.permissions
        and Permission.ACG_ASSIGN_PRODUCT in actor.permissions
    )
    if permission not in actor.permissions and not is_store_manager:
        raise AppError(403, "forbidden", "Permission denied.")


def _owner_team_key(owner_team: str) -> str:
    key = owner_team.strip().casefold()
    if key not in MANAGED_OWNER_PERMISSIONS:
        raise AppError(422, "owner_team_invalid", "Owner team is not supported.")
    return key
