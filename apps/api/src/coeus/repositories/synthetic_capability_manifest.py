"""Controlled team and analyst capability fixtures for the exercise workforce."""

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.repositories.synthetic_organisation_manifest import synthetic_posting_specs

TEAM_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "rfa_maritime": ("maritime_activity", "geospatial_reasoning", "pattern_analysis"),
    "rfa_land": ("land_forces", "order_of_battle", "terrain_assessment"),
    "rfa_cyber": ("cyber_threat", "technical_analysis", "infrastructure_mapping"),
    "rfa_regional": ("open_source_analysis", "regional_assessment", "source_validation"),
    "cm_open": ("open_source_collection", "source_discovery", "source_validation"),
    "cm_geo": ("geospatial_collection", "imagery_tasking", "change_detection"),
    "cm_requirements": (
        "collection_requirements",
        "source_coordination",
        "requirements_management",
    ),
}

ROUTING_TEAM_UNITS: dict[str, str] = {
    "RFA-MARITIME": "rfa_maritime",
    "RFA-CYBER": "rfa_cyber",
    "RFA-REGIONAL": "rfa_regional",
    "RFA-GEO": "rfa_land",
    "RFA-ECON": "rfa_regional",
    "RFA-INFRA": "rfa_land",
    "RFA-AIR": "rfa_land",
    "RFA-HEALTH": "rfa_regional",
    "RFA-SUPPLY": "rfa_maritime",
    "RFA-COUNTER": "rfa_land",
    "RFA-HUMAN": "rfa_regional",
    "RFA-AFRICA": "rfa_regional",
    "RFA-GENERAL": "rfa_land",
    "CM-GEO-MARITIME": "cm_geo",
    "CM-GEO-LAND": "cm_geo",
    "CM-GEO-AFRICA": "cm_geo",
    "CM-SIG-MARITIME": "cm_requirements",
    "CM-SIG-EAST": "cm_requirements",
    "CM-SIG-CYBER": "cm_requirements",
    "CM-OSINT-MEDIA": "cm_open",
    "CM-OSINT-COMMERCIAL": "cm_open",
    "CM-HUMINT-LIAISON": "cm_requirements",
    "CM-FININT": "cm_requirements",
    "CM-TECHINT": "cm_requirements",
    "CM-MASINT": "cm_requirements",
    "CM-CYBER-SENSOR": "cm_requirements",
    "CM-AVIATION": "cm_geo",
    "CM-SPACE": "cm_geo",
    "CM-BORDER": "cm_geo",
    "CM-CLIMATE": "cm_geo",
    "CM-DARKWEB": "cm_open",
    "CM-LANGUAGE": "cm_open",
    "CM-UAS": "cm_geo",
    "CM-INFRA": "cm_geo",
    "CM-SUPPLY": "cm_open",
    "CM-PATTERN": "cm_requirements",
    "CM-SANCTIONS": "cm_open",
    "CM-MEDICAL": "cm_open",
    "CM-COUNTER": "cm_requirements",
    "CM-GENERAL": "cm_requirements",
}


@dataclass(frozen=True)
class SyntheticTeamCapabilitySpec:
    unit_key: str
    capability_id: str
    proficiency: int

    @property
    def key(self) -> str:
        return f"{self.unit_key}:{self.capability_id}"

    @property
    def coverage_id(self) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"coeus:synthetic-team-capability:v2:{self.unit_key}:{self.capability_id}",
        )


@dataclass(frozen=True)
class SyntheticAnalystCompetencySpec:
    username: str
    capability_id: str
    proficiency: int

    @property
    def key(self) -> str:
        return f"{self.username}:{self.capability_id}"

    @property
    def competency_id(self) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"coeus:synthetic-analyst-competency:v2:{self.username}:{self.capability_id}",
        )


def synthetic_team_capabilities() -> tuple[SyntheticTeamCapabilitySpec, ...]:
    controlled = tuple(
        SyntheticTeamCapabilitySpec(unit_key, capability_id, 4 if index == 0 else 3)
        for unit_key, capabilities in TEAM_CAPABILITIES.items()
        for index, capability_id in enumerate(capabilities)
    )
    if len(ROUTING_TEAM_UNITS) != 40:
        raise RuntimeError("synthetic routing-team mapping is incomplete")
    routing = tuple(
        SyntheticTeamCapabilitySpec(unit_key, capability_id, 3)
        for capability_id, unit_key in ROUTING_TEAM_UNITS.items()
    )
    return (*controlled, *routing)


def synthetic_analyst_competencies() -> tuple[SyntheticAnalystCompetencySpec, ...]:
    rows: list[SyntheticAnalystCompetencySpec] = []
    analysts = []
    seen: set[str] = set()
    for item in synthetic_posting_specs():
        if item.username not in seen and (
            item.username == "analyst@example.test" or item.username.startswith("analyst.")
        ):
            analysts.append(item)
            seen.add(item.username)
    for analyst_index, posting in enumerate(analysts):
        capabilities = TEAM_CAPABILITIES[posting.unit_key]
        for capability_index, capability_id in enumerate(capabilities[:2]):
            proficiency = 4 if (analyst_index + capability_index) % 3 == 0 else 3
            rows.append(
                SyntheticAnalystCompetencySpec(
                    posting.username,
                    capability_id,
                    proficiency,
                )
            )
    return tuple(rows)
