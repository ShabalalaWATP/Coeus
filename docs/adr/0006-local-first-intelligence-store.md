# ADR 0006: Local-First Intelligence Store MVP

## Status

Accepted.

## Context

Sprint 5 introduces product management and search before database migrations,
object storage and vector indexes are available. The repository must stay public
safe and must not contain real product content.

## Decision

Use an in-memory Intelligence Store repository with synthetic seed products.
Model products, metadata and asset descriptors separately from real file bytes.
Expose service boundaries for ingestion, metadata validation, search, metadata
suggestions and controlled asset access.

Search uses deterministic local scoring across title, summary, tags, region and
source metadata. Access filtering happens before counts and facets are returned.
Controlled asset access returns a short-lived placeholder token only after the
same product access policy passes.

## Consequences

- Sprint 5 is fully testable without cloud services or real files.
- Future PostgreSQL, pgvector and object-storage implementations can replace the
  repository and search adapter without changing route contracts.
- No unauthorised product IDs, counts or asset object keys are exposed through
  search responses.
