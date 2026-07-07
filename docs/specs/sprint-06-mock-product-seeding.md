# Sprint 6 Spec: Mock Product Seeding

## Purpose

Create deterministic, public-repository-safe mock Intelligence Store products for
local development, tests and future search-agent work.

Sprint 6 generates product metadata and asset bytes at seed time. It does not
commit generated binaries or real intelligence examples.

## Scope

- Synthetic product generator package under `packages/mock-product-generators`.
- Seed script for generating a manifest and local asset tree.
- PDF, DOCX, PNG, JPEG, GeoJSON, KML, CSV and JSON mock assets.
- Product bundles containing linked document, image, geospatial and tabular
  assets.
- Deterministic product IDs, asset IDs, hashes, ACG assignments and access
  scenarios.
- Search-oriented metadata including tags, semantic labels, status, coverage
  dates and named search scenarios for future search tests.
- Regression tests proving the generated content is mock-labelled, deterministic
  and path-safe.

## Non-goals

- Real product upload, object storage ingestion or database persistence.
- Real classification markings, real source labels or operational templates.
- High-fidelity document rendering or imagery analysis fixtures.
- RFI Search Agent indexing. Sprint 7 consumes these generated products.

## Seed Counts

The default seed catalogue creates:

| Product family | Count | Asset formats |
|---|---:|---|
| Assessment reports | 40 | PDF, DOCX |
| Intelligence summaries | 40 | PDF, DOCX |
| Imagery products | 30 | PNG, JPEG |
| Geographic products | 25 | GeoJSON, KML |
| SIGINT-style mock records | 25 | CSV, JSON |
| Database extracts | 15 | CSV, JSON |
| Product bundles | 15 | PDF, PNG, GeoJSON, CSV |

This produces 190 products and 410 generated assets.

## Public Safety Rules

- Every product summary and generated asset includes `MOCK DATA ONLY`.
- Generated metadata uses fictional regions, teams, organisations and access
  groups.
- Generated paths are relative to the chosen output directory and never contain
  parent traversal.
- Large generated assets stay outside Git by default under `.local/`.
- The seed script supports a small smoke mode with one product per family.

## Acceptance Criteria

- `scripts/seed/seed_mock_products.py --small` writes a manifest and 16 generated
  assets.
- The default manifest contains 190 products and 410 asset descriptors.
- Product and asset IDs are deterministic across runs.
- Manifest products include tags, semantic labels, ACG codes, status and
  coverage dates.
- Named search scenarios provide example queries and expected metadata matches.
- PDF, DOCX, image, geospatial and tabular outputs carry mock markers.
- ACG definitions and access scenarios are present in the manifest.
- No real intelligence product content, credentials or operational examples are
  committed.
