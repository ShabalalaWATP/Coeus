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
    title = f"Mock {template.family.title()} Product {index:03d}"
    return SeedProduct(
        product_id=stable_id(f"product-{slug}"),
        reference=f"PROD-{reference_number}",
        title=title,
        summary=f"{MOCK_BANNER} synthetic {template.family} summary for {template.area_or_region}.",
        description=(
            f"{MOCK_BANNER} generated product for deterministic Sprint 6 seed data. "
            "It contains fictional entities and no operational content."
        ),
        product_type=template.product_type,
        source_type=template.source_type,
        owner_team=template.owner_team,
        area_or_region=template.area_or_region,
        classification_level=template.classification_level,
        releasability=("MOCK",),
        handling_caveats=(MOCK_BANNER,),
        tags=template.tags,
        acg_codes=template.acg_codes,
        access_scenario=_scenario_for_acgs(template.acg_codes),
        geojson_ref=f"assets/{slug}/{slug}.geojson"
        if "geojson" in template.asset_formats
        else None,
        bounding_box=(-7.0, 54.0, 31.0, 66.0)
        if "geojson" in template.asset_formats
        else None,
    )


def _scenario_for_acgs(acg_codes: tuple[str, ...]) -> str:
    for scenario in ACCESS_SCENARIOS:
        visible = set(scenario["visible_acg_codes"])
        if visible.intersection(acg_codes):
            return str(scenario["name"])
    return "administrator_only"
