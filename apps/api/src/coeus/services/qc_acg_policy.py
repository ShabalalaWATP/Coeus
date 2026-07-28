from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.tickets import TicketRecord
from coeus.repositories.access import AccessRepository


def requester_access_warning(access: AccessRepository, ticket: TicketRecord) -> str | None:
    """Warn ahead of release when the draft metadata would lock out the requester.

    Advisory only: the release step still hard-blocks with
    ``requester_access_lost``. Inline drafts without proposed ACGs return no
    warning because the QC officer chooses the metadata at approval time.
    """
    draft = ticket.draft_products[-1] if ticket.draft_products else None
    if draft is None or not draft.acg_ids:
        return None
    requester = access.get_user(ticket.requester_user_id)
    if requester is None:
        return None
    problems: list[str] = []
    if draft.classification_level > requester.clearance_level:
        problems.append("the classification sits above the requester's clearance")
    if not draft.acg_ids & access.active_acg_ids_for_user(requester.user_id):
        problems.append("the requester belongs to none of the proposed access control groups")
    if not problems:
        return None
    return (
        "Releasing with the draft metadata would prevent the requester reading "
        f"their own product: {'; '.join(problems)}."
    )


def validate_qc_acg_assignment(
    access: AccessRepository,
    actor: UserAccount,
    approval_acg_ids: frozenset[UUID],
    inherited_acg_ids: frozenset[UUID],
) -> None:
    actor_acgs = access.active_acg_ids_for_user(actor.user_id)
    for acg_id in approval_acg_ids:
        acg = access.get_acg(acg_id)
        if acg is None or not acg.is_active:
            raise AppError(409, "product_acg_required", "Products must use active ACGs.")
        if (
            Permission.PRODUCT_READ_RESTRICTED not in actor.permissions
            and acg_id not in actor_acgs
            and acg_id not in inherited_acg_ids
        ):
            raise AppError(403, "acg_not_authorised", "User cannot assign that ACG.")
