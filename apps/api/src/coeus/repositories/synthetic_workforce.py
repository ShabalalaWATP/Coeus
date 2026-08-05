"""Public-safe expansion rows for the canonical 53-person exercise cohort."""

from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.auth import RoleName
from coeus.repositories.synthetic_organisation_manifest import synthetic_unit_id

SyntheticUserRow = tuple[str, str, RoleName, bool]

EXPANDED_SEED_USER_ROWS: tuple[SyntheticUserRow, ...] = (
    ("admin.2@example.test", "Morgan Vale", RoleName.ADMINISTRATOR, True),
    ("customer.3@example.test", "Rowan Ellery", RoleName.USER, True),
    ("customer.4@example.test", "Tessa North", RoleName.USER, True),
    ("customer.5@example.test", "Isaac Fen", RoleName.USER, True),
    ("customer.6@example.test", "Mira Calder", RoleName.USER, True),
    ("jioc.3@example.test", "Devin Shaw", RoleName.JIOC_TEAM_MEMBER, True),
    ("rfa.lead.2@example.test", "Ainsley March", RoleName.RFA_MANAGER, True),
    ("rfa.lead.3@example.test", "Robin Cade", RoleName.RFA_MANAGER, True),
    ("rfa.lead.4@example.test", "Ellis Ward", RoleName.RFA_MANAGER, True),
    ("rfa.coordinator@example.test", "Sasha Lennox", RoleName.RFA_TEAM_MEMBER, True),
    ("cm.lead.2@example.test", "Dana Pryce", RoleName.COLLECTION_MANAGER, True),
    ("cm.lead.3@example.test", "Kellan Frost", RoleName.COLLECTION_MANAGER, True),
    ("cm.deputy@example.test", "Nia Mercer", RoleName.COLLECTION_MANAGER, True),
    ("cm.coordinator@example.test", "Jules Arden", RoleName.COLLECTION_TEAM_MEMBER, True),
    ("store.curator@example.test", "Avery Quill", RoleName.INTELLIGENCE_STORE_MANAGER, True),
    ("qc.reviewer.2@example.test", "Blair Sutton", RoleName.QUALITY_CONTROL_MANAGER, True),
    ("qc.reviewer.3@example.test", "Casey Venn", RoleName.QUALITY_CONTROL_MANAGER, True),
    ("analyst.5@example.test", "Ari Bell", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.6@example.test", "Emery Stone", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.7@example.test", "Finley Moss", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.8@example.test", "Harper Glen", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.9@example.test", "Indigo Carr", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.10@example.test", "Jamie Rook", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.11@example.test", "Kai Rowan", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.12@example.test", "Logan Wren", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.13@example.test", "Micah Dale", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.14@example.test", "Noa Hales", RoleName.INTELLIGENCE_ANALYST, False),
    ("analyst.15@example.test", "Orla Reed", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.16@example.test", "Perry Knox", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.17@example.test", "Quinn Alder", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.18@example.test", "Remy Brook", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.19@example.test", "Shay Rowan", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.20@example.test", "Tobin Vale", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.21@example.test", "Uma Voss", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.22@example.test", "Wynne Hart", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.23@example.test", "Yael Finch", RoleName.INTELLIGENCE_ANALYST, True),
    ("analyst.24@example.test", "Zuri Penn", RoleName.INTELLIGENCE_ANALYST, False),
)


ANALYST_CLEARANCE_LEVELS: dict[str, int] = {
    username: 2 + (index % 2)
    for index, (username, _name, role, _active) in enumerate(EXPANDED_SEED_USER_ROWS)
    if role is RoleName.INTELLIGENCE_ANALYST
}
ANALYST_CLEARANCE_LEVELS.update(
    {
        "analyst@example.test": 3,
        "analyst.2@example.test": 2,
        "analyst.3@example.test": 3,
        "analyst.4@example.test": 2,
    }
)


def synthetic_clearance_level(username: str) -> int:
    """Return a varied, non-authoritative exercise clearance projection."""
    return ANALYST_CLEARANCE_LEVELS.get(username.casefold(), 3)


def synthetic_user_id(username: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-user:v2:{username.casefold()}")


def synthetic_team_id(name: str) -> UUID:
    """Return the canonical unit identity for a seeded organisational team.

    The legacy team repository and the relational organisation projection are
    two views of the same exercise teams. Keeping one identity prevents an
    assignment accepted by the UI authority checks from being rejected by the
    canonical ownership transaction.
    """
    unit_key = _CANONICAL_TEAM_UNIT_KEYS.get(name.casefold())
    if unit_key is not None:
        return synthetic_unit_id(unit_key)
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-team:v2:{name.casefold()}")


_CANONICAL_TEAM_UNIT_KEYS = {
    "rfa assessment team": "rfa_maritime",
    "all-source and land assessment": "rfa_land",
    "cyber and technical assessment": "rfa_cyber",
    "regional and open-source assessment": "rfa_regional",
    "collection management team": "cm_open",
    "geospatial collection": "cm_geo",
    "collection requirements and coordination": "cm_requirements",
    "jioc routing cell": "jioc",
    "quality control cell": "qc",
}
