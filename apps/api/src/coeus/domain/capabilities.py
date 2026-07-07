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
