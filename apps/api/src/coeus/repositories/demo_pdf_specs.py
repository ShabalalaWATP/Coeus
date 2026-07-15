"""Canonical synthetic source text for the live-demo PDF corpus."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PdfScenario:
    acg_code: str
    country: str
    focus: str
    region: str
    tags: tuple[str, ...]
    labels: tuple[str, ...]


@dataclass(frozen=True)
class DemoPdfSeed:
    seed_name: str
    reference: str
    title: str
    summary: str
    description: str
    product_type: str
    source_type: str
    owner_team: str
    area_or_region: str
    classification_level: int
    tags: frozenset[str]
    semantic_labels: frozenset[str]
    acg_code: str
    time_period: tuple[str, str]


PDF_SCENARIOS = (
    PdfScenario(
        "ACG-RU-LAND",
        "Russia",
        "Army land systems",
        "Fictional eastern exercise area",
        ("russia", "army", "tanks", "armour", "artillery", "mechanised"),
        ("russia", "land-warfare", "armour", "artillery"),
    ),
    PdfScenario(
        "ACG-RU-EW",
        "Russia",
        "electronic warfare",
        "Fictional northern exercise area",
        ("russia", "ew", "electronic-warfare", "jamming", "spectrum", "radar"),
        ("russia", "electronic-warfare", "spectrum"),
    ),
    PdfScenario(
        "ACG-RU-SIGINT",
        "Russia",
        "SIGINT collection",
        "Fictional western exercise area",
        ("russia", "sigint", "signals", "elint", "emitters", "communications"),
        ("russia", "sigint", "electronic-warfare"),
    ),
    PdfScenario(
        "ACG-RU-MISSILE",
        "Russia",
        "missile and air-defence systems",
        "Fictional central exercise area",
        ("russia", "missiles", "ballistic", "cruise", "air-defence", "rocket-artillery"),
        ("russia", "missile", "air-defence", "artillery"),
    ),
    PdfScenario(
        "ACG-RU-UAS",
        "Russia",
        "uncrewed aerial systems",
        "Fictional border exercise area",
        ("russia", "drones", "uas", "reconnaissance", "loitering", "counter-uas"),
        ("russia", "uas", "aviation"),
    ),
    PdfScenario(
        "ACG-IR-LAND",
        "Iran",
        "Army land systems",
        "Fictional plateau exercise area",
        ("iran", "army", "tanks", "armour", "artillery", "logistics"),
        ("iran", "land-warfare", "armour", "artillery"),
    ),
    PdfScenario(
        "ACG-IR-EW",
        "Iran",
        "electronic warfare",
        "Fictional desert exercise area",
        ("iran", "ew", "electronic-warfare", "jamming", "spectrum", "communications"),
        ("iran", "electronic-warfare", "spectrum"),
    ),
    PdfScenario(
        "ACG-IR-SIGINT",
        "Iran",
        "SIGINT collection",
        "Fictional coastal exercise area",
        ("iran", "sigint", "signals", "radar", "emitters", "communications"),
        ("iran", "sigint", "electronic-warfare"),
    ),
    PdfScenario(
        "ACG-IR-MISSILE",
        "Iran",
        "missile and rocket systems",
        "Fictional southern exercise area",
        ("iran", "missiles", "ballistic", "cruise", "rockets", "artillery"),
        ("iran", "missile", "air-defence", "artillery"),
    ),
    PdfScenario(
        "ACG-IR-CYBER",
        "Iran",
        "cyber operations",
        "Synthetic regional networks",
        ("iran", "cyber", "intrusion", "malware", "network", "infrastructure"),
        ("iran", "cyber", "infrastructure"),
    ),
    PdfScenario(
        "ACG-CN-LAND",
        "China",
        "Army land systems",
        "Fictional inland exercise area",
        ("china", "army", "tanks", "armour", "artillery", "amphibious"),
        ("china", "land-warfare", "armour", "artillery"),
    ),
    PdfScenario(
        "ACG-CN-EW",
        "China",
        "electronic warfare",
        "Fictional joint exercise area",
        ("china", "ew", "electronic-warfare", "jamming", "spectrum", "radar"),
        ("china", "electronic-warfare", "spectrum"),
    ),
    PdfScenario(
        "ACG-CN-SIGINT",
        "China",
        "SIGINT collection",
        "Fictional maritime exercise area",
        ("china", "sigint", "signals", "elint", "emitters", "communications"),
        ("china", "sigint", "electronic-warfare"),
    ),
    PdfScenario(
        "ACG-CN-UAS",
        "China",
        "uncrewed aerial systems",
        "Fictional littoral exercise area",
        ("china", "drones", "uas", "swarming", "reconnaissance", "counter-uas"),
        ("china", "uas", "aviation"),
    ),
    PdfScenario(
        "ACG-CN-CYBER",
        "China",
        "cyber operations",
        "Synthetic regional networks",
        ("china", "cyber", "intrusion", "malware", "network", "supply-chain"),
        ("china", "cyber", "supply-chain"),
    ),
)

PDF_VARIANTS = (
    "Order of Battle Review",
    "Equipment Readiness Assessment",
    "Training Activity Summary",
    "Logistics and Sustainment Note",
    "Indicators and Warning Digest",
    "Capability Development Assessment",
    "Tactics and Procedures Review",
    "Command Decision Brief",
    "Collection Gap Assessment",
    "Thirty-Day Outlook",
)

PDF_SCENARIO_COUNTS = (9, 9, 9, 9, 9, 9, 10, 10, 10, 10, 10, 10, 10, 10, 10)


def demo_pdf_seeds() -> tuple[DemoPdfSeed, ...]:
    seeds: list[DemoPdfSeed] = []
    reference = 3000
    for scenario_index, (scenario, count) in enumerate(
        zip(PDF_SCENARIOS, PDF_SCENARIO_COUNTS, strict=True)
    ):
        for variant_index, variant in enumerate(PDF_VARIANTS[:count]):
            reference += 1
            month = (variant_index % 6) + 1
            seeds.append(_seed(scenario, scenario_index, variant, variant_index, reference, month))
    return tuple(seeds)


def _seed(
    scenario: PdfScenario,
    scenario_index: int,
    variant: str,
    variant_index: int,
    reference: int,
    month: int,
) -> DemoPdfSeed:
    focus = scenario.focus
    title = f"{scenario.country} {focus}: {variant}"
    terms = ", ".join(scenario.tags)
    return DemoPdfSeed(
        seed_name=f"corpus-{scenario_index:02d}-{variant_index:02d}",
        reference=f"PROD-{reference}",
        title=title,
        summary=(
            f"MOCK DATA ONLY synthetic exercise {variant.casefold()} covering {focus}. "
            "It supports retrieval and access-control demonstrations only."
        ),
        description=(
            f"MOCK DATA ONLY. Fictional analysis for {scenario.region}. Searchable themes: "
            f"{terms}. No real units, locations, sources or operational claims are represented."
        ),
        product_type="assessment_report" if variant_index % 3 else "intelligence_summary",
        source_type="finished_assessment" if variant_index % 3 else "current_intelligence",
        owner_team="RFA" if variant_index % 2 else "Collection",
        area_or_region=scenario.region,
        classification_level=2 + ((scenario_index + variant_index) % 2),
        tags=frozenset({*scenario.tags, "mock-data", "synthetic-exercise"}),
        semantic_labels=frozenset(scenario.labels),
        acg_code=scenario.acg_code,
        time_period=(f"2026-{month:02d}-01", f"2026-{month:02d}-28"),
    )
