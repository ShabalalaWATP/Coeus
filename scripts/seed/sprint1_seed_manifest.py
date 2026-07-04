"""Emit a deterministic, public-repository-safe Sprint 1 seed manifest."""

from __future__ import annotations

import json


def build_seed_manifest() -> dict[str, object]:
    return {
        "banner": "MOCK DATA ONLY",
        "users": ["mock-customer", "mock-rfa-manager", "mock-analyst", "mock-qc-manager"],
        "acgs": ["mock-regional-acg", "mock-product-review-acg"],
        "projects": ["mock-project-workspace"],
        "tickets": ["mock-rfi-ticket"],
        "products": ["mock-assessment-report", "mock-geographic-layer"],
        "note": "Database insertion starts when Sprint 3 to Sprint 5 schemas exist.",
    }


def main() -> None:
    print(json.dumps(build_seed_manifest(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

