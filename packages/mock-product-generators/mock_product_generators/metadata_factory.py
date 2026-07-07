from collections.abc import Iterable
from uuid import UUID, uuid5

from .models import MOCK_BANNER, ProductTemplate, SeedProduct

SEED_NAMESPACE = UUID("9945d7c4-58ac-46d2-a22d-5d66a8403151")

ACG_DEFINITIONS = (
    {
        "code": "ACG-ALPHA-REGIONAL",
        "name": "Alpha Regional",
        "description": "Regional mock access group for customer-facing assessments.",
    },
    {
        "code": "ACG-BRAVO-COLLECTION",
        "name": "Bravo Collection",
        "description": "Collection mock access group for source-derived products.",
    },
    {
        "code": "ACG-CHARLIE-ASSESSMENT",
        "name": "Charlie Assessment",
        "description": "Assessment mock access group for analytic products.",
    },
    {
        "code": "ACG-DELTA-GEO",
        "name": "Delta Geo",
        "description": "Geospatial mock access group for map layers.",
    },
    {
        "code": "ACG-ECHO-DATA",
        "name": "Echo Data",
        "description": "Structured data mock access group for extracts and bundles.",
    },
)

ACCESS_SCENARIOS = (
    {
        "name": "customer_regional",
        "description": "Customer with Alpha Regional membership can discover regional products.",
        "visible_acg_codes": ("ACG-ALPHA-REGIONAL",),
    },
    {
        "name": "collection_team",
        "description": "Collection team member sees Bravo Collection products only.",
        "visible_acg_codes": ("ACG-BRAVO-COLLECTION",),
    },
    {
        "name": "geo_specialist",
        "description": "Geo specialist sees Delta Geo layers with matching clearance.",
        "visible_acg_codes": ("ACG-DELTA-GEO",),
    },
    {
        "name": "data_steward",
        "description": "Data steward sees Echo Data extracts and bundles.",
        "visible_acg_codes": ("ACG-ECHO-DATA",),
    },
)

SEARCH_SCENARIOS = (
    {
        "name": "maritime_port_disruption",
        "query": "baltic port disruption maritime supply",
        "expectedSemanticLabels": ("maritime", "supply-chain"),
        "expectedTags": ("ports", "maritime"),
        "visibleAccessScenario": "customer_regional",
    },
    {
        "name": "cyber_energy_intrusion",
        "query": "cyber intrusion energy network",
        "expectedSemanticLabels": ("cyber", "infrastructure"),
        "expectedTags": ("cyber", "energy"),
        "visibleAccessScenario": "data_steward",
    },
    {
        "name": "geospatial_border_crossing",
        "query": "border crossing geospatial map",
        "expectedSemanticLabels": ("border", "geospatial"),
        "expectedTags": ("border", "map"),
        "visibleAccessScenario": "geo_specialist",
    },
    {
        "name": "collection_sensor_activity",
        "query": "sensor radar collection coastal",
        "expectedSemanticLabels": ("collection", "sigint"),
        "expectedTags": ("sensor", "coastal"),
        "visibleAccessScenario": "collection_team",
    },
)

DOMAIN_VARIANTS = (
    {
        "topic": "Baltic port disruption",
        "area": "Baltic ports",
        "tags": ("ports", "maritime", "supply-chain"),
        "labels": ("maritime", "supply-chain"),
    },
    {
        "topic": "North Sea lane congestion",
        "area": "North Sea lanes",
        "tags": ("shipping", "maritime", "logistics"),
        "labels": ("maritime", "supply-chain"),
    },
    {
        "topic": "coastal sensor activity",
        "area": "Fictional coastal grid",
        "tags": ("sensor", "coastal", "radar"),
        "labels": ("collection", "sigint"),
    },
    {
        "topic": "Delta training range access",
        "area": "Delta training range",
        "tags": ("map", "terrain", "geographic"),
        "labels": ("geospatial",),
    },
    {
        "topic": "Echo logistics district flows",
        "area": "Echo logistics district",
        "tags": ("database", "logistics", "freight"),
        "labels": ("supply-chain",),
    },
    {
        "topic": "Arctic power infrastructure",
        "area": "Arctic energy corridor",
        "tags": ("energy", "power", "infrastructure"),
        "labels": ("infrastructure", "environment"),
    },
    {
        "topic": "aviation route change",
        "area": "Mock northern air corridor",
        "tags": ("aviation", "aircraft", "runway"),
        "labels": ("aviation",),
    },
    {
        "topic": "public media narratives",
        "area": "Open source media space",
        "tags": ("osint", "media", "public"),
        "labels": ("osint",),
    },
    {
        "topic": "health logistics strain",
        "area": "Fictional medical supply hub",
        "tags": ("health", "medical", "supply"),
        "labels": ("health", "supply-chain"),
    },
    {
        "topic": "border checkpoint pressure",
        "area": "Mock border corridor",
        "tags": ("border", "checkpoint", "migration"),
        "labels": ("border",),
    },
    {
        "topic": "cyber intrusion indicators",
        "area": "Synthetic network enclave",
        "tags": ("cyber", "network", "credential"),
        "labels": ("cyber",),
    },
    {
        "topic": "flood impact on rail",
        "area": "Fictional flood plain",
        "tags": ("flood", "rail", "weather"),
        "labels": ("environment", "infrastructure"),
    },
)

TEMPLATES = (
    ProductTemplate(
        "assessment",
        "assessment_report",
        "finished_assessment",
        "RFA",
        "Baltic ports",
        ("ACG-ALPHA-REGIONAL",),
        2,
        ("pdf", "docx"),
        ("assessment", "regional", "mock"),
    ),
    ProductTemplate(
        "summary",
        "intelligence_summary",
        "finished_assessment",
        "RFA",
        "North Sea lanes",
        ("ACG-CHARLIE-ASSESSMENT",),
        3,
        ("pdf", "docx"),
        ("summary", "assessment", "mock"),
    ),
    ProductTemplate(
        "imagery",
        "satellite_imagery_product",
        "imagery",
        "Collection",
        "Fictional coastal grid",
        ("ACG-BRAVO-COLLECTION",),
        3,
        ("png", "jpg"),
        ("imagery", "coastal", "mock"),
    ),
    ProductTemplate(
        "geographic",
        "geographic_product",
        "geospatial",
        "Collection",
        "Delta training range",
        ("ACG-DELTA-GEO",),
        2,
        ("geojson", "kml"),
        ("geographic", "layer", "mock"),
    ),
    ProductTemplate(
        "sigint",
        "sigint_mock",
        "sensor",
        "Collection",
        "Mock relay zone",
        ("ACG-BRAVO-COLLECTION", "ACG-ECHO-DATA"),
        3,
        ("csv", "json"),
        ("sigint", "sensor", "mock"),
    ),
    ProductTemplate(
        "database",
        "database_extract",
        "database_extract",
        "RFA",
        "Echo logistics district",
        ("ACG-ECHO-DATA",),
        2,
        ("csv", "json"),
        ("database", "extract", "mock"),
    ),
    ProductTemplate(
        "bundle",
        "product_bundle",
        "mixed_bundle",
        "RFA",
        "Joint exercise area",
        ("ACG-ALPHA-REGIONAL", "ACG-ECHO-DATA"),
        3,
        ("pdf", "png", "geojson", "csv"),
        ("bundle", "joint", "mock"),
    ),
)


def stable_id(name: str) -> UUID:
    return uuid5(SEED_NAMESPACE, name)


def product_shells(counts: dict[str, int]) -> tuple[SeedProduct, ...]:
    products: list[SeedProduct] = []
    reference = 2000
    for template in TEMPLATES:
        for index in range(1, counts[template.family] + 1):
            reference += 1
            products.append(_product_from_template(template, index, reference))
    return tuple(products)


def acg_codes_for_products(products: Iterable[SeedProduct]) -> tuple[str, ...]:
    return tuple(sorted({code for product in products for code in product.acg_codes}))


def _product_from_template(
    template: ProductTemplate, index: int, reference_number: int
) -> SeedProduct:
    slug = f"{template.family}-{index:03d}"
    variant = DOMAIN_VARIANTS[(index - 1) % len(DOMAIN_VARIANTS)]
    title = f"Mock {template.family.title()} Product {index:03d}: {variant['topic']}"
    tags = _merged(template.tags, variant["tags"])
    semantic_labels = _merged(template.tags, variant["labels"])
    period_start, period_end = _coverage_window(index)
    return SeedProduct(
        product_id=stable_id(f"product-{slug}"),
        reference=f"PROD-{reference_number}",
        title=title,
        summary=(
            f"{MOCK_BANNER} synthetic {template.family} summary for "
            f"{variant['area']} covering {variant['topic']}."
        ),
        description=(
            f"{MOCK_BANNER} generated product for deterministic Sprint 6 seed data. "
            f"Fictional search terms include {', '.join(tags)}. "
            "It contains fictional entities and no operational content."
        ),
        product_type=template.product_type,
        source_type=template.source_type,
        owner_team=template.owner_team,
        area_or_region=str(variant["area"]),
        classification_level=template.classification_level,
        releasability=("MOCK",),
        handling_caveats=(MOCK_BANNER,),
        tags=tags,
        semantic_labels=semantic_labels,
        acg_codes=template.acg_codes,
        access_scenario=_scenario_for_acgs(template.acg_codes),
        status="published",
        time_period_start=period_start,
        time_period_end=period_end,
        geojson_ref=f"assets/{slug}/{slug}.geojson"
        if "geojson" in template.asset_formats
        else None,
        bounding_box=(-7.0, 54.0, 31.0, 66.0) if "geojson" in template.asset_formats else None,
    )


def _merged(*values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({item for group in values for item in group}))


def _coverage_window(index: int) -> tuple[str, str]:
    year = 2025 + ((index - 1) // 12)
    month = ((index - 1) % 12) + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-28"


def _scenario_for_acgs(acg_codes: tuple[str, ...]) -> str:
    for scenario in ACCESS_SCENARIOS:
        visible = set(scenario["visible_acg_codes"])
        if visible.intersection(acg_codes):
            return str(scenario["name"])
    return "administrator_only"
