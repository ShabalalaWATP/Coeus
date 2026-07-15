"""Export the deterministic synthetic PDF corpus for repository demos."""

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path

from coeus.repositories.access import stable_seed_id
from coeus.repositories.demo_pdf_catalogue import build_pdf_corpus
from coeus.repositories.demo_pdf_specs import demo_pdf_seeds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output: Path = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    seeds = demo_pdf_seeds()
    acg_ids = {
        seed.acg_code: stable_seed_id(f"export-{seed.acg_code}") for seed in seeds
    }
    products, objects, _ = build_pdf_corpus(acg_ids, stable_seed_id("export-author"))
    content_by_key = dict(objects)
    manifest: list[dict[str, object]] = []
    for seed, product in zip(seeds, products, strict=True):
        asset = product.assets[0]
        content = content_by_key[asset.object_key]
        filename = f"{product.reference}-{_slug(product.metadata.title)}.pdf"
        (output / filename).write_bytes(content)
        manifest.append(
            {
                "acg": seed.acg_code,
                "filename": filename,
                "reference": product.reference,
                "sha256": sha256(content).hexdigest(),
                "sizeBytes": len(content),
                "title": product.metadata.title,
            }
        )
    (output.parent / "manifest.json").write_text(
        json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8"
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


if __name__ == "__main__":
    main()
