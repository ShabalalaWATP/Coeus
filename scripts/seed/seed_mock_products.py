"""Generate deterministic Sprint 6 mock products and seed manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GENERATOR_ROOT = (
    Path(__file__).resolve().parents[2] / "packages" / "mock-product-generators"
)
sys.path.insert(0, str(GENERATOR_ROOT))

from mock_product_generators import DEFAULT_PRODUCT_COUNTS, write_mock_catalog  # noqa: E402


def main() -> None:
    args = _parse_args()
    counts = _counts_from_args(args)
    manifest = write_mock_catalog(
        args.output_dir, counts, write_assets=not args.manifest_only
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "productCount": manifest["productCount"],
                "assetCount": manifest["assetCount"],
                "banner": manifest["banner"],
            },
            indent=2,
            sort_keys=True,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".local/mock-products"),
        help="Directory for generated mock assets and manifest.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Build metadata and hashes without writing asset files.",
    )
    parser.add_argument(
        "--small",
        action="store_true",
        help="Generate one product per category for fast local smoke checks.",
    )
    return parser.parse_args()


def _counts_from_args(args: argparse.Namespace) -> dict[str, int]:
    if not args.small:
        return dict(DEFAULT_PRODUCT_COUNTS)
    return {family: 1 for family in DEFAULT_PRODUCT_COUNTS}


if __name__ == "__main__":
    main()
