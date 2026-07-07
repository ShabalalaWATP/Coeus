from coeus.domain.capabilities import CapabilityDepartment, CapabilityTeam

RFA_TEAM_SPECS = (
    ("RFA-MARITIME", "Maritime Assessment Cell", "maritime port vessel shipping arctic baltic"),
    ("RFA-CYBER", "Cyber Threat Assessment Cell", "cyber malware intrusion network digital"),
    ("RFA-REGIONAL", "Regional Stability Assessment Cell", "regional stability political crisis"),
    ("RFA-GEO", "Geospatial Assessment Cell", "geospatial map imagery terrain border"),
    ("RFA-ECON", "Economic Pressure Assessment Cell", "economic sanctions finance trade"),
    ("RFA-INFRA", "Critical Infrastructure Assessment Cell", "infrastructure energy rail power"),
    ("RFA-AIR", "Air And Space Assessment Cell", "aviation air missile satellite space"),
    ("RFA-HEALTH", "Health Security Assessment Cell", "health medical disease biosecurity"),
    ("RFA-SUPPLY", "Supply Chain Assessment Cell", "supply logistics port freight"),
    ("RFA-COUNTER", "Counter-Proliferation Assessment Cell", "proliferation nuclear chemical"),
    ("RFA-HUMAN", "Human Terrain Assessment Cell", "population humanitarian migration"),
    ("RFA-GENERAL", "General Assessment Triage Cell", "assessment report brief analysis"),
)

CM_TEAM_SPECS = (
    (
        "CM-GEO-MARITIME",
        "Maritime Imagery Collection Cell",
        "imagery satellite port vessel maritime",
    ),
    ("CM-GEO-LAND", "Land GEOINT Tasking Cell", "geospatial terrain border facility map"),
    ("CM-SIG-MARITIME", "Maritime Signals Collection Cell", "sigint signals vessel emitter radar"),
    ("CM-SIG-CYBER", "Cyber Signals Collection Cell", "network beacon malware intrusion cyber"),
    ("CM-OSINT-MEDIA", "Open Media Exploitation Cell", "media social public narrative osint"),
    (
        "CM-OSINT-COMMERCIAL",
        "Commercial Data Exploitation Cell",
        "commercial shipping trade registry",
    ),
    ("CM-HUMINT-LIAISON", "HUMINT Liaison Cell", "human source liaison access intent"),
    ("CM-FININT", "Financial Intelligence Collection Cell", "finance sanctions payment ownership"),
    ("CM-TECHINT", "Technical Intelligence Collection Cell", "technical equipment platform sensor"),
    ("CM-MASINT", "Measurement And Signature Cell", "signature measurement radar acoustic"),
    ("CM-CYBER-SENSOR", "Cyber Sensor Coordination Cell", "sensor telemetry endpoint cyber"),
    ("CM-AVIATION", "Aviation Collection Coordination Cell", "air aviation flight runway aircraft"),
    ("CM-SPACE", "Space Domain Collection Cell", "space satellite orbital launch"),
    ("CM-BORDER", "Border Monitoring Collection Cell", "border crossing checkpoint migration"),
    ("CM-CLIMATE", "Environmental Collection Cell", "climate weather flood wildfire"),
    ("CM-DARKWEB", "Dark Web Collection Cell", "darkweb forum illicit credential"),
    ("CM-LANGUAGE", "Language Exploitation Cell", "translation language document transcript"),
    ("CM-UAS", "Uncrewed Systems Collection Cell", "drone uas overhead tactical"),
    ("CM-INFRA", "Infrastructure Monitoring Cell", "energy power pipeline rail infrastructure"),
    ("CM-SUPPLY", "Supply Chain Collection Cell", "supply logistics freight port cargo"),
    ("CM-PATTERN", "Pattern Of Life Collection Cell", "pattern activity movement routine"),
    ("CM-SANCTIONS", "Sanctions Evasion Collection Cell", "sanctions evasion vessel company"),
    ("CM-MEDICAL", "Medical Collection Coordination Cell", "medical hospital disease health"),
    (
        "CM-COUNTER",
        "Counter-Proliferation Collection Cell",
        "nuclear chemical missile proliferation",
    ),
    ("CM-GENERAL", "Collection Coordination Triage Cell", "collection collect tasking source"),
)


class CapabilityCatalogue:
    def __init__(self) -> None:
        self._rfa_teams = tuple(_rfa_team(*spec) for spec in RFA_TEAM_SPECS)
        self._cm_teams = tuple(_cm_team(*spec) for spec in CM_TEAM_SPECS)

    def best_rfa_team(self, terms: frozenset[str]) -> CapabilityTeam:
        return _best(self._rfa_teams, terms) or self._rfa_teams[-1]

    def best_cm_team(self, terms: frozenset[str]) -> CapabilityTeam | None:
        return _best(self._cm_teams, terms)

    def default_cm_team(self) -> CapabilityTeam:
        return self._cm_teams[-1]

    def rfa_teams(self) -> tuple[CapabilityTeam, ...]:
        return self._rfa_teams

    def cm_teams(self) -> tuple[CapabilityTeam, ...]:
        return self._cm_teams


def _rfa_team(team_id: str, name: str, keywords: str) -> CapabilityTeam:
    return CapabilityTeam(
        team_id=team_id,
        name=name,
        department=CapabilityDepartment.RFA,
        keywords=frozenset(keywords.split()),
        work_packages=(
            f"Validate the requirement with {name}.",
            "Identify evidence gaps and assumptions.",
            "Prepare analyst handover notes.",
        ),
    )


def _cm_team(team_id: str, name: str, keywords: str) -> CapabilityTeam:
    source = name.replace(" Cell", "").replace("Collection ", "").casefold()
    return CapabilityTeam(
        team_id=team_id,
        name=name,
        department=CapabilityDepartment.CM,
        keywords=frozenset(keywords.split()),
        work_packages=(
            f"Confirm collection feasibility with {name}.",
            "Define tasking constraints and source access.",
        ),
        source_labels=(source, "collection manager coordination"),
    )


def _best(teams: tuple[CapabilityTeam, ...], terms: frozenset[str]) -> CapabilityTeam | None:
    ranked = sorted(
        ((len(team.keywords.intersection(terms)), team.name, team) for team in teams),
        key=lambda item: (-item[0], item[1]),
    )
    score, _name, team = ranked[0]
    return team if score > 0 else None
