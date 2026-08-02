"""Synthetic Ukraine-Russia scenarios for the local downloadable PDF corpus."""

from coeus.repositories.demo_pdf_specs import DemoPdfSeed, PdfScenario

UKRAINE_RUSSIA_SCENARIOS = (
    PdfScenario(
        "ACG-RU-LAND",
        "Ukraine-Russia exercise",
        "Kursk border-area ground activity",
        "Kursk border exercise area (synthetic)",
        ("kursk", "border-activity", "ground-forces", "armour", "logistics"),
        ("ukraine", "russia", "kursk", "land-warfare"),
    ),
    PdfScenario(
        "ACG-RU-LAND",
        "Ukraine-Russia exercise",
        "northern Donbas mechanised movement",
        "Northern Donbas exercise corridor (synthetic)",
        ("donbas", "mechanised", "armour", "movement", "ground-forces"),
        ("ukraine", "russia", "donbas", "armour"),
    ),
    PdfScenario(
        "ACG-RU-LAND",
        "Ukraine-Russia exercise",
        "Donetsk artillery and sustainment activity",
        "Donetsk exercise area (synthetic)",
        ("donetsk", "artillery", "sustainment", "ammunition", "logistics"),
        ("ukraine", "russia", "donetsk", "artillery"),
    ),
    PdfScenario(
        "ACG-RU-LAND",
        "Ukraine-Russia exercise",
        "Luhansk logistics-route activity",
        "Luhansk exercise area (synthetic)",
        ("luhansk", "logistics", "transport", "supply-routes", "readiness"),
        ("ukraine", "russia", "luhansk", "logistics"),
    ),
    PdfScenario(
        "ACG-RU-LAND",
        "Ukraine-Russia exercise",
        "Kharkiv border-area warning indicators",
        "Kharkiv border exercise area (synthetic)",
        ("kharkiv", "border-activity", "warning", "armour", "reconnaissance"),
        ("ukraine", "russia", "kharkiv", "indicators-warning"),
    ),
    PdfScenario(
        "ACG-RU-LAND",
        "Ukraine-Russia exercise",
        "Zaporizhzhia southern-corridor activity",
        "Zaporizhzhia exercise corridor (synthetic)",
        ("zaporizhzhia", "southern-front", "artillery", "defences", "logistics"),
        ("ukraine", "russia", "zaporizhzhia", "land-warfare"),
    ),
    PdfScenario(
        "ACG-RU-MISSILE",
        "Ukraine-Russia exercise",
        "Kyiv missile warning patterns",
        "Kyiv regional warning exercise (synthetic)",
        ("kyiv", "missiles", "cruise-missile", "warning", "air-defence"),
        ("ukraine", "russia", "kyiv", "missile", "air-defence"),
    ),
    PdfScenario(
        "ACG-RU-UAS",
        "Ukraine-Russia exercise",
        "Kyiv drone and counter-UAS activity",
        "Kyiv regional air exercise (synthetic)",
        ("kyiv", "drones", "uas", "counter-uas", "air-defence"),
        ("ukraine", "russia", "kyiv", "uas", "counter-uas"),
    ),
    PdfScenario(
        "ACG-RU-UAS",
        "Ukraine-Russia exercise",
        "Black Sea missile and maritime-drone activity",
        "Black Sea exercise area (synthetic)",
        ("black-sea", "maritime-drones", "missiles", "uas", "warning"),
        ("ukraine", "russia", "black-sea", "maritime", "uas"),
    ),
    PdfScenario(
        "ACG-RU-UAS",
        "Ukraine-Russia exercise",
        "Moscow drone warning and counter-UAS activity",
        "Moscow regional warning exercise (synthetic)",
        ("moscow", "drones", "warning", "counter-uas", "air-defence"),
        ("russia", "moscow", "uas", "counter-uas"),
    ),
    PdfScenario(
        "ACG-RU-MISSILE",
        "Ukraine-Russia exercise",
        "Moscow regional air-defence activity",
        "Moscow regional air-defence exercise (synthetic)",
        ("moscow", "air-defence", "radar", "missile-defence", "readiness"),
        ("russia", "moscow", "air-defence", "missile"),
    ),
    PdfScenario(
        "ACG-RU-EW",
        "Ukraine-Russia exercise",
        "Donbas electronic-warfare activity",
        "Donbas spectrum exercise area (synthetic)",
        ("donbas", "electronic-warfare", "jamming", "spectrum", "communications"),
        ("ukraine", "russia", "donbas", "electronic-warfare"),
    ),
)

REPORT_VARIANTS = (
    ("Situation Update", "intelligence_summary", "current_intelligence"),
    ("Activity Pattern Assessment", "assessment_report", "finished_assessment"),
    ("Indicators and Warning Note", "intelligence_summary", "current_intelligence"),
    ("Effects and Warning Digest", "assessment_report", "finished_assessment"),
    ("Logistics and Readiness Note", "assessment_report", "finished_assessment"),
    ("Thirty-Day Outlook", "intelligence_summary", "current_intelligence"),
)

REPORT_PERIODS = (
    ("2025-01-01", "2025-01-31"),
    ("2025-04-01", "2025-04-30"),
    ("2025-08-01", "2025-08-31"),
    ("2025-12-01", "2025-12-31"),
    ("2026-03-01", "2026-03-31"),
    ("2026-07-01", "2026-07-31"),
)


def demo_ukraine_pdf_seeds() -> tuple[DemoPdfSeed, ...]:
    """Return 72 stable, public-repository-safe mock report definitions."""

    seeds: list[DemoPdfSeed] = []
    reference = 3200
    for scenario_index, scenario in enumerate(UKRAINE_RUSSIA_SCENARIOS):
        for variant_index, ((variant, product_type, source_type), period) in enumerate(
            zip(REPORT_VARIANTS, REPORT_PERIODS, strict=True)
        ):
            reference += 1
            terms = ", ".join(scenario.tags)
            seeds.append(
                DemoPdfSeed(
                    seed_name=f"ukraine-{scenario_index:02d}-{variant_index:02d}",
                    reference=f"PROD-{reference}",
                    title=f"Ukraine-Russia {scenario.focus}: {variant}",
                    summary=(
                        f"{variant} covering {scenario.focus} during an invented exercise timeline."
                    ),
                    description=(
                        f"Fictional conflict-monitoring exercise for "
                        f"{scenario.region}. Searchable themes: {terms}. No real event, unit, "
                        "source, coordinate or operational claim is represented."
                    ),
                    product_type=product_type,
                    source_type=source_type,
                    owner_team="RFA" if variant_index % 2 else "Collection",
                    area_or_region=scenario.region,
                    classification_level=2 + ((scenario_index + variant_index) % 2),
                    tags=frozenset(
                        {
                            *scenario.tags,
                            "ukraine",
                            "russia",
                            "synthetic-conflict",
                            "mock-data",
                            "synthetic-exercise",
                        }
                    ),
                    semantic_labels=frozenset(scenario.labels),
                    acg_code=scenario.acg_code,
                    time_period=period,
                )
            )
    return tuple(seeds)
