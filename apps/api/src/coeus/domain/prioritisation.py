"""Deterministic internal priority ranking.

All registry content is synthetic demo weighting (MOCK DATA ONLY): fictional
operations and units, and a coarse region tiering used to demonstrate how the
platform would order competing requests. The assessment is a pure function of
the intake, so recomputing it always gives the same answer, and every score
carries prefixed reason tags in the same idiom as the search scorers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Imported for typing only; tickets.py imports PriorityAssessment at
    # runtime, so a runtime import here would be circular.
    from coeus.domain.tickets import IntakeDetails

WEIGHT_LEVEL = 0.35
WEIGHT_REGION = 0.25
WEIGHT_UNIT = 0.20
WEIGHT_OPERATION = 0.20

PRIORITY_LEVEL_WEIGHTS = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.55,
    "routine": 0.35,
    "low": 0.2,
}
MISSING_LEVEL_WEIGHT = 0.2

# Region tiers, matched as substrings of the stated area or region.
REGION_TIERS = (
    ("tier-1", 1.0, ("russia", "kaliningrad", "baltic", "arctic", "eastern europe", "black sea")),
    ("tier-2", 0.75, ("middle east", "north africa", "eastern mediterranean")),
    ("tier-3", 0.5, ("indo-pacific", "south china sea", "west africa")),
)
DEFAULT_REGION_WEIGHT = 0.25

# Requesting-unit categories in the demanded order of precedence:
# special forces > intelligence > carrier groups > field army > air bases.
UNIT_CATEGORIES = (
    ("special-forces", 1.0, ("task group kestrel", "special reconnaissance", "special forces")),
    (
        "intelligence",
        0.85,
        ("joint intelligence fusion cell", "defence intelligence", "intelligence"),
    ),
    ("carrier-group", 0.7, ("carrier strike group", "strike group")),
    ("field-army", 0.55, ("field army", "brigade", "battalion", "regiment", "armoured")),
    ("air-base", 0.4, ("air station", "air base", "raf ", "squadron")),
)
DEFAULT_UNIT_WEIGHT = 0.25

# Fictional operation registry with type weights: special forces operations
# outrank conventional ones, standing tasks and exercises.
OPERATION_REGISTRY = (
    ("special-forces", 1.0, ("onyx talon", "sable wraith")),
    ("conventional", 0.7, ("iron bulwark", "grey heron")),
    ("standing-task", 0.5, ("harbour sentinel",)),
    ("exercise", 0.3, ("baltic resolve",)),
)
UNREGISTERED_OPERATION_WEIGHT = 0.4
MISSING_OPERATION_WEIGHT = 0.2

TIER_THRESHOLDS = (("P1", 0.8), ("P2", 0.6), ("P3", 0.4))


@dataclass(frozen=True)
class PriorityAssessment:
    score: float
    tier: str
    reasons: tuple[str, ...]


def assess_intake(intake: IntakeDetails) -> PriorityAssessment:
    level_weight, level_reason = _level(intake.priority)
    region_weight, region_reason = _region(intake.area_or_region)
    unit_weight, unit_reason = _unit(intake.requesting_unit)
    operation_weight, operation_reason = _operation(intake.supported_operation)
    score = round(
        WEIGHT_LEVEL * level_weight
        + WEIGHT_REGION * region_weight
        + WEIGHT_UNIT * unit_weight
        + WEIGHT_OPERATION * operation_weight,
        4,
    )
    return PriorityAssessment(
        score=score,
        tier=_tier(score),
        reasons=(level_reason, region_reason, unit_reason, operation_reason),
    )


def _tier(score: float) -> str:
    for tier, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "P4"


def _level(priority: str | None) -> tuple[float, str]:
    stated = (priority or "").strip().casefold()
    if stated in PRIORITY_LEVEL_WEIGHTS:
        return PRIORITY_LEVEL_WEIGHTS[stated], f"priority:level:{stated}"
    return MISSING_LEVEL_WEIGHT, "priority:level:unstated"


def _region(area_or_region: str | None) -> tuple[float, str]:
    stated = (area_or_region or "").casefold()
    for tier, weight, names in REGION_TIERS:
        for name in names:
            if name in stated:
                return weight, f"priority:region:{tier}:{name.replace(' ', '-')}"
    return DEFAULT_REGION_WEIGHT, "priority:region:standard"


def _unit(requesting_unit: str | None) -> tuple[float, str]:
    stated = (requesting_unit or "").casefold()
    if not stated.strip():
        return DEFAULT_UNIT_WEIGHT, "priority:unit:unstated"
    for category, weight, cues in UNIT_CATEGORIES:
        if any(cue in stated for cue in cues):
            return weight, f"priority:unit:{category}"
    return DEFAULT_UNIT_WEIGHT, "priority:unit:uncategorised"


def _operation(supported_operation: str | None) -> tuple[float, str]:
    stated = (supported_operation or "").casefold()
    if not stated.strip():
        return MISSING_OPERATION_WEIGHT, "priority:operation:none"
    for kind, weight, names in OPERATION_REGISTRY:
        for name in names:
            if name in stated:
                return weight, f"priority:operation:{kind}:{name.replace(' ', '-')}"
    return UNREGISTERED_OPERATION_WEIGHT, "priority:operation:unregistered"
