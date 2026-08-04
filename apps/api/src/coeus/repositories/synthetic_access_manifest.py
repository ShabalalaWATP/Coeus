"""Least-privilege exercise ACG memberships for the synthetic analysts."""

from collections.abc import Callable
from uuid import UUID

from coeus.domain.access import AccessControlGroup, AccessControlGroupMembership
from coeus.domain.auth import UserAccount
from coeus.domain.organisation import MembershipState
from coeus.repositories.synthetic_organisation_manifest import synthetic_posting_specs

_TEAM_ACGS = {
    "rfa_maritime": ("ACG-MAR-GEOINT", "ACG-EU-OSINT", "ACG-RU-UAS"),
    "rfa_land": ("ACG-RU-LAND", "ACG-EU-GEOINT", "ACG-RU-MISSILE"),
    "rfa_cyber": ("ACG-EU-CYBER", "ACG-CN-CYBER", "ACG-RU-EW"),
    "rfa_regional": ("ACG-EU-OSINT", "ACG-EU-HUMINT", "ACG-RU-LAND"),
    "cm_open": ("ACG-EU-OSINT", "ACG-ME-OSINT", "ACG-RU-UAS"),
    "cm_geo": ("ACG-MAR-GEOINT", "ACG-EU-GEOINT", "ACG-RU-MISSILE"),
    "cm_requirements": ("ACG-EU-SIGINT", "ACG-EU-GEOINT", "ACG-EU-OSINT"),
}


def synthetic_analyst_acg_codes() -> dict[str, frozenset[str]]:
    """Return explicit access variation without using profile text as authority."""
    result: dict[str, frozenset[str]] = {}
    for posting in synthetic_posting_specs():
        if posting.username in result or not posting.username.startswith("analyst"):
            continue
        codes: tuple[str, ...] = _TEAM_ACGS.get(posting.unit_key, ())
        if posting.state in {MembershipState.ENDED, MembershipState.SUSPENDED}:
            codes = codes[:1]
        result[posting.username] = frozenset(codes)
    return result


def merge_synthetic_analyst_access(
    acgs: dict[UUID, AccessControlGroup],
    memberships: set[AccessControlGroupMembership],
    resolve_user: Callable[[str], UserAccount | None],
) -> None:
    acg_ids = {item.code: item.acg_id for item in acgs.values() if item.is_active}
    for username, codes in synthetic_analyst_acg_codes().items():
        user = resolve_user(username)
        if user is None:
            continue
        memberships.update(
            AccessControlGroupMembership(acg_ids[code], user.user_id)
            for code in codes
            if code in acg_ids
        )
