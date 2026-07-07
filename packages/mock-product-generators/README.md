# Coeus Mock Product Generators

Synthetic product generation utilities for Sprint 6. Generated mock products
carry a visible `MOCK DATA ONLY` marker or equivalent metadata.

## Usage

```powershell
python scripts/seed/seed_mock_products.py --output-dir .local/mock-products
python scripts/seed/seed_mock_products.py --small --output-dir .local/mock-products-smoke
```

The default catalogue creates 190 products and 410 generated assets. The small
mode creates one product per family and is intended for fast smoke checks.

Each manifest entry includes product metadata for search and access-control
tests: product type, source type, owner team, region, classification level,
releasability, caveats, tags, semantic labels, ACG codes, status, coverage
dates, hashes and asset paths. The manifest also includes named search scenarios
with example queries and expected tags or semantic labels.

Generated assets are deterministic and public-repository-safe. They should stay
outside Git under `.local/` or another ignored local directory.
