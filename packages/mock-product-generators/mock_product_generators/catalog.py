from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Callable

from .documents import write_docx, write_pdf
from .geospatial import write_geojson, write_kml
from .images import write_jpeg, write_png
from .metadata_factory import (
    ACG_DEFINITIONS,
    ACCESS_SCENARIOS,
    product_shells,
    stable_id,
)
from .models import MOCK_BANNER, SeedAsset, SeedProduct
from .tabular import write_csv, write_json

DEFAULT_PRODUCT_COUNTS = {
    "assessment": 40,
    "summary": 40,
    "imagery": 30,
    "geographic": 25,
    "sigint": 25,
    "database": 15,
    "bundle": 15,
}

ASSET_TYPES: dict[str, tuple[str, str, str, Callable[[Path, SeedProduct], None]]] = {
    "pdf": ("pdf", "application/pdf", ".pdf", write_pdf),
    "docx": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
        write_docx,
    ),
    "png": ("image", "image/png", ".png", write_png),
    "jpg": ("image", "image/jpeg", ".jpg", write_jpeg),
    "geojson": ("geojson", "application/geo+json", ".geojson", write_geojson),
    "kml": ("kml", "application/vnd.google-earth.kml+xml", ".kml", write_kml),
    "csv": ("csv", "text/csv", ".csv", write_csv),
    "json": ("json", "application/json", ".json", write_json),
}


def build_mock_catalog(counts: dict[str, int] | None = None) -> tuple[SeedProduct, ...]:
    requested_counts = counts or DEFAULT_PRODUCT_COUNTS
    _validate_counts(requested_counts)
    return product_shells(requested_counts)


def write_mock_catalog(
    output_dir: Path,
    counts: dict[str, int] | None = None,
    *,
    write_assets: bool = True,
) -> dict[str, object]:
    products = []
    for product in build_mock_catalog(counts):
        products.append(_write_product(output_dir, product, write_assets=write_assets))
    manifest = _manifest(products)
    output_dir.mkdir(parents=True, exist_ok=True)
    return manifest


def manifest_product(product: SeedProduct) -> dict[str, object]:
    return {
        "id": str(product.product_id),
        "reference": product.reference,
        "title": product.title,
        "summary": product.summary,
        "description": product.description,
        "productType": product.product_type,
        "sourceType": product.source_type,
        "ownerTeam": product.owner_team,
        "areaOrRegion": product.area_or_region,
        "classificationLevel": product.classification_level,
        "releasability": list(product.releasability),
        "handlingCaveats": list(product.handling_caveats),
        "tags": list(product.tags),
        "acgCodes": list(product.acg_codes),
        "accessScenario": product.access_scenario,
        "geojsonRef": product.geojson_ref,
        "boundingBox": product.bounding_box,
        "assets": [
            {
                "id": str(asset.asset_id),
                "name": asset.name,
                "assetType": asset.asset_type,
                "mimeType": asset.mime_type,
                "sizeBytes": asset.size_bytes,
                "sha256": asset.sha256,
                "relativePath": asset.relative_path,
            }
            for asset in product.assets
        ],
    }


def _write_product(
    output_dir: Path, product: SeedProduct, *, write_assets: bool
) -> SeedProduct:
    assets: list[SeedAsset] = []
    family = product.reference.lower()
    slug = _slug(product.title)
    for asset_format in _formats_for_product(product):
        asset_type, mime_type, extension, writer = ASSET_TYPES[asset_format]
        asset_name = f"{slug}{extension}"
        relative_path = Path("assets") / family / asset_name
        asset_path = output_dir / relative_path
        if write_assets:
            writer(asset_path, product)
            content = asset_path.read_bytes()
        else:
            content = f"{MOCK_BANNER}:{product.reference}:{asset_format}".encode(
                "utf-8"
            )
        assets.append(
            SeedAsset(
                asset_id=stable_id(f"asset-{product.reference}-{asset_format}"),
                name=asset_name,
                asset_type=asset_type,
                mime_type=mime_type,
                size_bytes=len(content),
                sha256=sha256(content).hexdigest(),
                relative_path=relative_path.as_posix(),
            )
        )
    geojson_asset = next(
        (asset for asset in assets if asset.asset_type == "geojson"),
        None,
    )
    return replace(
        product,
        assets=tuple(assets),
        geojson_ref=geojson_asset.relative_path
        if geojson_asset
        else product.geojson_ref,
    )


def _formats_for_product(product: SeedProduct) -> tuple[str, ...]:
    if product.product_type == "assessment_report":
        return ("pdf", "docx")
    if product.product_type == "intelligence_summary":
        return ("pdf", "docx")
    if product.product_type == "satellite_imagery_product":
        return ("png", "jpg")
    if product.product_type == "geographic_product":
        return ("geojson", "kml")
    if product.product_type in {"sigint_mock", "database_extract"}:
        return ("csv", "json")
    if product.product_type == "product_bundle":
        return ("pdf", "png", "geojson", "csv")
    raise ValueError(f"Unsupported product type: {product.product_type}")


def _manifest(products: list[SeedProduct]) -> dict[str, object]:
    asset_count = sum(len(product.assets) for product in products)
    return {
        "banner": MOCK_BANNER,
        "version": 1,
        "productCount": len(products),
        "assetCount": asset_count,
        "acgs": list(ACG_DEFINITIONS),
        "accessScenarios": list(ACCESS_SCENARIOS),
        "products": [manifest_product(product) for product in products],
    }


def _validate_counts(counts: dict[str, int]) -> None:
    missing = set(DEFAULT_PRODUCT_COUNTS) - set(counts)
    unknown = set(counts) - set(DEFAULT_PRODUCT_COUNTS)
    if missing or unknown:
        raise ValueError(
            f"Invalid product count keys. Missing={missing}; unknown={unknown}"
        )
    invalid = {family: count for family, count in counts.items() if count < 0}
    if invalid:
        raise ValueError(f"Product counts must be non-negative: {invalid}")


def _slug(value: str) -> str:
    return (
        value.casefold()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
    )
