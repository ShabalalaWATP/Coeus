"""Deterministic object bytes for the base synthetic Store catalogue."""

import json
from base64 import b64decode

from coeus.domain.store import StoreAsset, StoreProduct
from coeus.repositories.demo_pdf import build_demo_pdf_bytes

_PNG_PIXEL = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def build_demo_asset_bytes(product: StoreProduct, asset: StoreAsset) -> bytes:
    """Return bounded, public-repository-safe content matching the asset type."""
    if asset.mime_type == "application/pdf":
        return build_demo_pdf_bytes(product)
    if asset.mime_type == "image/png":
        return _PNG_PIXEL
    if asset.mime_type == "application/geo+json":
        return _geojson_bytes(product)
    if asset.mime_type == "text/csv":
        return _csv_bytes(product)
    return (
        "MOCK DATA ONLY\n"
        f"reference={product.reference}\n"
        f"asset={asset.name}\n"
        "synthetic_parameter=demo-only\n"
    ).encode()


def _geojson_bytes(product: StoreProduct) -> bytes:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "notice": "MOCK DATA ONLY",
                    "reference": product.reference,
                },
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            }
        ],
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _csv_bytes(product: StoreProduct) -> bytes:
    return (
        "notice,reference,indicator,value\n"
        f'MOCK DATA ONLY,{product.reference},synthetic activity,"demo only"\n'
    ).encode()
