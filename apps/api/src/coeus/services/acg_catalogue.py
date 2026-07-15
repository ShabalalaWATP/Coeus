"""Bounded, presentation-safe access-group catalogue projections."""

from math import ceil
from uuid import UUID

from coeus.domain.access import AccessControlGroup
from coeus.repositories.access import AccessRepository
from coeus.repositories.acg_applications import AcgApplicationRepository


def catalogue_page(
    access: AccessRepository, page: int, page_size: int, query: str
) -> tuple[tuple[AccessControlGroup, ...], int, int]:
    active = tuple(acg for acg in access.list_acgs() if acg.is_active)
    if search := query.strip().casefold():
        active = tuple(
            acg for acg in active if search in f"{acg.code} {acg.name} {acg.description}".casefold()
        )
    start = (page - 1) * page_size
    pages = total_pages(active, page_size)
    return active[start : start + page_size], len(active), pages


def active_manager_names(
    access: AccessRepository, workflows: AcgApplicationRepository, acg_id: UUID
) -> tuple[str, ...]:
    users = (access.get_user(user_id) for user_id in workflows.admin_user_ids(acg_id))
    return tuple(sorted(user.display_name for user in users if user is not None and user.is_active))


def total_pages(items: tuple[object, ...], page_size: int) -> int:
    return ceil(len(items) / page_size) if items else 0
