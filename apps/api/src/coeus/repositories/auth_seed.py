from collections.abc import Iterable

from coeus.domain.auth import RoleName


def seed_user_specs() -> Iterable[tuple[str, str, frozenset[RoleName], bool]]:
    return (
        (
            "admin@example.test",
            "Admin Operator",
            frozenset({RoleName.ADMINISTRATOR}),
            True,
        ),
        ("user@example.test", "Customer User", frozenset({RoleName.USER}), True),
        (
            "colleague@example.test",
            "Customer Colleague",
            frozenset({RoleName.USER}),
            True,
        ),
        (
            "jioc.team@example.test",
            "JIOC Team Member",
            frozenset({RoleName.JIOC_TEAM_MEMBER}),
            True,
        ),
        (
            "rfa.manager@example.test",
            "RFA Manager",
            frozenset({RoleName.RFA_MANAGER}),
            True,
        ),
        (
            "rfa.team@example.test",
            "RFA Team Member",
            frozenset({RoleName.RFA_TEAM_MEMBER}),
            True,
        ),
        (
            "collection.manager@example.test",
            "CM Manager",
            frozenset({RoleName.COLLECTION_MANAGER}),
            True,
        ),
        (
            "collection.team@example.test",
            "CM Team Member",
            frozenset({RoleName.COLLECTION_TEAM_MEMBER}),
            True,
        ),
        (
            "store.manager@example.test",
            "Intelligence Store Manager",
            frozenset({RoleName.INTELLIGENCE_STORE_MANAGER}),
            True,
        ),
        (
            "analyst@example.test",
            "Analyst",
            frozenset({RoleName.INTELLIGENCE_ANALYST}),
            True,
        ),
        (
            "analyst.maritime@example.test",
            "Maritime Assessment Analyst",
            frozenset({RoleName.INTELLIGENCE_ANALYST}),
            True,
        ),
        (
            "analyst.cyber@example.test",
            "Cyber Threat Analyst",
            frozenset({RoleName.INTELLIGENCE_ANALYST}),
            True,
        ),
        (
            "analyst.geo@example.test",
            "Geospatial Assessment Analyst",
            frozenset({RoleName.INTELLIGENCE_ANALYST}),
            True,
        ),
        (
            "qc.manager@example.test",
            "QC Manager",
            frozenset({RoleName.QUALITY_CONTROL_MANAGER}),
            True,
        ),
        ("disabled@example.test", "Disabled User", frozenset({RoleName.USER}), False),
    )
