"""Synthetic local user identities and safe legacy-seed reconciliation."""

from collections.abc import Iterable
from dataclasses import dataclass, replace

from coeus.domain.auth import RoleName, UserAccount


@dataclass(frozen=True)
class SeedUserSpec:
    username: str
    display_name: str
    roles: frozenset[RoleName]
    is_active: bool = True
    legacy_usernames: tuple[str, ...] = ()
    legacy_display_names: tuple[str, ...] = ()


def seed_user_specs() -> tuple[SeedUserSpec, ...]:
    """Return public-repository-safe fictional workforce identities."""
    return (
        _spec("admin@example.test", "Andy Robertson", RoleName.ADMINISTRATOR, "Admin Operator"),
        _spec("user@example.test", "John McGinn", RoleName.USER, "Customer User"),
        _spec("colleague@example.test", "Billy Gilmour", RoleName.USER, "Customer Colleague"),
        _spec(
            "jioc.team@example.test",
            "Scott McTominay",
            RoleName.JIOC_TEAM_MEMBER,
            "JIOC Team Member",
        ),
        _spec(
            "rfa.manager@example.test",
            "Kieran Tierney",
            RoleName.RFA_MANAGER,
            "RFA Manager",
        ),
        _spec(
            "rfa.team@example.test",
            "Ryan Christie",
            RoleName.RFA_TEAM_MEMBER,
            "RFA Team Member",
        ),
        _spec(
            "collection.manager@example.test",
            "Grant Hanley",
            RoleName.COLLECTION_MANAGER,
            "CM Manager",
            additional_legacy_display_names=("Collection Manager",),
        ),
        _spec(
            "collection.team@example.test",
            "Kenny McLean",
            RoleName.COLLECTION_TEAM_MEMBER,
            "CM Team Member",
            additional_legacy_display_names=("Collection Team Member",),
        ),
        _spec(
            "store.manager@example.test",
            "Craig Gordon",
            RoleName.INTELLIGENCE_STORE_MANAGER,
            "Intelligence Store Manager",
        ),
        _spec(
            "analyst@example.test",
            "Lewis Ferguson",
            RoleName.INTELLIGENCE_ANALYST,
            "Analyst",
            additional_legacy_display_names=("Intelligence Analyst",),
        ),
        _spec(
            "analyst.2@example.test",
            "Nathan Patterson",
            RoleName.INTELLIGENCE_ANALYST,
            "Maritime Assessment Analyst",
            legacy_usernames=("analyst.maritime@example.test",),
        ),
        _spec(
            "analyst.3@example.test",
            "Ben Doak",
            RoleName.INTELLIGENCE_ANALYST,
            "Cyber Threat Analyst",
            legacy_usernames=("analyst.cyber@example.test",),
        ),
        _spec(
            "analyst.4@example.test",
            "Che Adams",
            RoleName.INTELLIGENCE_ANALYST,
            "Geospatial Assessment Analyst",
            legacy_usernames=("analyst.geo@example.test",),
        ),
        _spec(
            "qc.manager@example.test",
            "Angus Gunn",
            RoleName.QUALITY_CONTROL_MANAGER,
            "QC Manager",
        ),
        _spec(
            "disabled@example.test",
            "James Forrest",
            RoleName.USER,
            "Disabled User",
            is_active=False,
        ),
    )


def reconcile_seed_user_identities(users: Iterable[UserAccount]) -> tuple[UserAccount, ...]:
    """Rename recognised legacy seed values without changing account authority."""
    reconciled = list(users)
    by_username = {user.username.casefold(): index for index, user in enumerate(reconciled)}

    for spec in seed_user_specs():
        index = by_username.get(spec.username.casefold())
        if index is None:
            for legacy_username in spec.legacy_usernames:
                index = by_username.get(legacy_username.casefold())
                if index is not None:
                    break
        if index is None:
            continue

        current = reconciled[index]
        display_name = current.display_name
        if display_name in spec.legacy_display_names:
            display_name = spec.display_name
        migrated = replace(current, username=spec.username, display_name=display_name)
        if migrated == current:
            continue
        reconciled[index] = migrated
        by_username.pop(current.username.casefold(), None)
        by_username[migrated.username.casefold()] = index

    return tuple(reconciled)


def _spec(
    username: str,
    display_name: str,
    role: RoleName,
    legacy_display_name: str,
    *,
    legacy_usernames: tuple[str, ...] = (),
    additional_legacy_display_names: tuple[str, ...] = (),
    is_active: bool = True,
) -> SeedUserSpec:
    return SeedUserSpec(
        username=username,
        display_name=display_name,
        roles=frozenset({role}),
        is_active=is_active,
        legacy_usernames=legacy_usernames,
        legacy_display_names=(legacy_display_name, *additional_legacy_display_names),
    )
