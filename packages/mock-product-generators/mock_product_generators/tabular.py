import csv
import json
from pathlib import Path

from .models import MOCK_BANNER, SeedProduct


def write_csv(path: Path, product: SeedProduct) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["banner", "reference", "entity", "score"]
        )
        writer.writeheader()
        for index in range(1, 4):
            writer.writerow(
                {
                    "banner": MOCK_BANNER,
                    "reference": product.reference,
                    "entity": f"fictional-entity-{index}",
                    "score": index * 10,
                }
            )


def write_json(path: Path, product: SeedProduct) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "banner": MOCK_BANNER,
        "reference": product.reference,
        "title": product.title,
        "records": [
            {"entity": f"fictional-entity-{index}", "score": index * 10}
            for index in range(1, 4)
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
