"""Stable specialist ACG definitions for the synthetic local demo corpus."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from coeus.domain.access import AccessControlGroup, AccessControlGroupMembership

THEMED_ACG_REGIONS = (
    ("EU", "European"),
    ("AF", "African"),
    ("ME", "Middle Eastern"),
    ("AP", "Asia-Pacific"),
    ("NA", "North American"),
    ("SA", "South American"),
    ("AR", "Arctic"),
    ("MAR", "Maritime"),
)
THEMED_ACG_DISCIPLINES = ("Cyber", "HUMINT", "SIGINT", "GEOINT", "OSINT")


@dataclass(frozen=True)
class DemoAcgSpec:
    code: str
    name: str
    description: str


SPECIALIST_ACG_SPECS = (
    DemoAcgSpec("ACG-RU-LAND", "Russia Land Systems", "Land systems reporting."),
    DemoAcgSpec("ACG-RU-EW", "Russia Electronic Warfare", "Electronic warfare reporting."),
    DemoAcgSpec("ACG-RU-SIGINT", "Russia SIGINT", "Signals intelligence reporting."),
    DemoAcgSpec("ACG-RU-MISSILE", "Russia Missile Systems", "Missile systems reporting."),
    DemoAcgSpec("ACG-RU-UAS", "Russia Uncrewed Systems", "Uncrewed systems reporting."),
    DemoAcgSpec("ACG-IR-LAND", "Iran Land Systems", "Land systems reporting."),
    DemoAcgSpec("ACG-IR-EW", "Iran Electronic Warfare", "Electronic warfare reporting."),
    DemoAcgSpec("ACG-IR-SIGINT", "Iran SIGINT", "Signals intelligence reporting."),
    DemoAcgSpec("ACG-IR-MISSILE", "Iran Missile Systems", "Missile systems reporting."),
    DemoAcgSpec("ACG-IR-CYBER", "Iran Cyber", "Cyber reporting."),
    DemoAcgSpec("ACG-CN-LAND", "China Land Systems", "Land systems reporting."),
    DemoAcgSpec("ACG-CN-EW", "China Electronic Warfare", "Electronic warfare reporting."),
    DemoAcgSpec("ACG-CN-SIGINT", "China SIGINT", "Signals intelligence reporting."),
    DemoAcgSpec("ACG-CN-UAS", "China Uncrewed Systems", "Uncrewed systems reporting."),
    DemoAcgSpec("ACG-CN-CYBER", "China Cyber", "Cyber reporting."),
)

BILLY_DENIED_ACG_CODES = frozenset({"ACG-RU-SIGINT", "ACG-CN-CYBER"})


def specialist_acgs(
    owner_user_id: UUID, stable_id: Callable[[str], UUID]
) -> tuple[AccessControlGroup, ...]:
    return tuple(
        AccessControlGroup(
            acg_id=stable_id(spec.code),
            code=spec.code,
            name=spec.name,
            description=spec.description,
            owner_user_id=owner_user_id,
            is_active=True,
        )
        for spec in SPECIALIST_ACG_SPECS
    )


def merge_demo_access(
    acgs: dict[UUID, AccessControlGroup],
    memberships: set[AccessControlGroupMembership],
    owner_user_id: UUID,
    billy_user_id: UUID,
    stable_id: Callable[[str], UUID],
) -> bool:
    changed = False
    for acg in specialist_acgs(owner_user_id, stable_id):
        if acg.acg_id not in acgs:
            acgs[acg.acg_id] = acg
            memberships.add(AccessControlGroupMembership(acg.acg_id, owner_user_id))
            changed = True
    for acg in acgs.values():
        membership = AccessControlGroupMembership(acg.acg_id, billy_user_id)
        if acg.code not in BILLY_DENIED_ACG_CODES and membership not in memberships:
            memberships.add(membership)
            changed = True
    return changed
