# ADR 0007: Standard-Library Mock Product Generators

## Status

Accepted.

## Context

Sprint 6 needs PDF, DOCX, image, geospatial and tabular mock products, but the
repository must remain public safe and local-first. Pulling in document or image
generation dependencies would increase supply-chain surface area before the
application needs production-grade rendering.

## Decision

Build the mock product generators with Python standard-library modules only.
Generate minimal valid-enough seed assets with explicit `MOCK DATA ONLY` markers,
stable IDs and stable content hashes. Keep the generator package isolated from
the API application so future persistence and ingestion work can consume the
manifest without coupling route handlers to seed logic.

The seed script writes generated files under a caller-provided output directory,
defaulting to `.local/mock-products`, and writes a JSON manifest describing
products, ACGs, access scenarios and asset metadata.

## Consequences

- Seed generation runs without extra Python dependencies or cloud services.
- Generated assets are deterministic and safe to recreate in tests and local
  environments.
- The assets are suitable for metadata, access-control and search development,
  but not for high-fidelity rendering validation.
- Future ingestion work can replace the file writers with richer generators
  behind the same manifest contract if needed.
