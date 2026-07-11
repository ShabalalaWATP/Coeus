from dataclasses import dataclass
from enum import StrEnum


class CapabilityDepartment(StrEnum):
    RFA = "rfa"
    CM = "cm"


@dataclass(frozen=True)
class CapabilityTeam:
    team_id: str
    name: str
    department: CapabilityDepartment
    keywords: frozenset[str]
    work_packages: tuple[str, ...]
    source_labels: tuple[str, ...] = ()
    # Intelligence disciplines the team works in (IMINT, SIGINT, OSINT, ...).
    disciplines: frozenset[str] = frozenset()
    # Regions the team covers; "global" marks region-agnostic teams.
    regions: frozenset[str] = frozenset()
    # Relative importance weight (0..1) used by the recommendation scorer.
    rank: float = 0.5


@dataclass(frozen=True)
class CandidateTeam:
    team_id: str
    name: str
    score: float
    reasons: tuple[str, ...]
