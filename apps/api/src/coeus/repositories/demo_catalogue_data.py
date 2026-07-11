"""Static mappings for the local demo store catalogue (MOCK DATA ONLY).

Data only; the product specs live in ``demo_catalogue_specs.py`` and the
builder in ``demo_catalogue.py``.
"""

DEMO_REFERENCE_BASE = 2000
BOUNDING_BOX = (-30.0, 20.0, 60.0, 72.0)

# discipline -> (product_type, asset_kind, keyword tags, semantic labels)
DISCIPLINE_META: dict[str, tuple[str, str, tuple[str, ...], tuple[str, ...]]] = {
    "CYBER": ("assessment_report", "pdf", ("cyber", "threat", "network"), ("cyber", "threat")),
    "HUMINT": (
        "intelligence_summary",
        "pdf",
        ("humint", "source", "network"),
        ("humint", "assessment"),
    ),
    "SIGINT": (
        "sigint_mock",
        "sigint",
        ("sigint", "signals", "collection"),
        ("sigint", "collection"),
    ),
    "GEOINT": (
        "satellite_imagery_product",
        "image",
        ("geoint", "imagery", "terrain"),
        ("geoint", "imagery"),
    ),
    "OSINT": (
        "intelligence_summary",
        "pdf",
        ("osint", "open-source", "media"),
        ("osint", "assessment"),
    ),
}

# asset_kind -> ((name suffix, asset_type, mime_type, preview_kind, size_bytes), ...)
ASSET_KINDS: dict[str, tuple[tuple[str, str, str, str, int], ...]] = {
    "pdf": (("report.pdf", "pdf", "application/pdf", "pdf_metadata", 18_000),),
    "image": (("imagery.png", "image", "image/png", "image", 240_000),),
    "geojson": (("layer.geojson", "geojson", "application/geo+json", "geojson", 32_000),),
    "csv": (("dataset.csv", "csv", "text/csv", "text_metadata", 48_000),),
    "sigint": (("parametric.dat", "dataset", "application/octet-stream", "text_metadata", 96_000),),
    "bundle": (
        ("brief.pdf", "pdf", "application/pdf", "pdf_metadata", 18_000),
        ("overlay.png", "image", "image/png", "image", 240_000),
        ("indicators.csv", "csv", "text/csv", "text_metadata", 48_000),
    ),
}

# Asset kinds that carry a geospatial layer reference.
GEOJSON_KINDS = frozenset({"geojson"})

# product_type -> semantic labels for the showcase products.
TYPE_LABELS: dict[str, tuple[str, ...]] = {
    "assessment_report": ("assessment", "finished"),
    "intelligence_summary": ("summary", "current"),
    "satellite_imagery_product": ("imagery", "geospatial"),
    "geographic_product": ("geospatial", "overlay"),
    "database_extract": ("dataset", "structured"),
    "product_bundle": ("bundle", "multi-source"),
    "finished_output": ("fused", "all-source"),
    "sigint_mock": ("sigint", "collection"),
}

# region code -> area/region label
REGION_AREAS: dict[str, str] = {
    "EU": "Eastern Europe",
    "AF": "Sahel, Africa",
    "ME": "Eastern Mediterranean",
    "AP": "South China Sea",
    "NA": "North America",
    "SA": "Andean region",
    "AR": "Arctic Circle",
    "MAR": "North Atlantic approaches",
}
