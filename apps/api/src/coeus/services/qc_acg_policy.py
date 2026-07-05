from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.repositories.access import SeedAccessRepository


def validate_qc_acg_assignment(
    access: SeedAccessRepository,
    actor: UserAccount,
    approval_acg_ids: frozenset[UUID],
    project_acg_ids: frozenset[UUID],
) -> None:
    actor_acgs = access.active_acg_ids_for_user(actor.user_id)
    for acg_id in approval_acg_ids:
        acg = access.get_acg(acg_id)
        if acg is None or not acg.is_active:
            raise AppError(409, "product_acg_required", "Products must use active ACGs.")
        if (
            Permission.PRODUCT_READ_RESTRICTED not in actor.permissions
            and acg_id not in actor_acgs
            and acg_id not in project_acg_ids
        ):
            raise AppError(403, "acg_not_authorised", "User cannot assign that ACG.")
