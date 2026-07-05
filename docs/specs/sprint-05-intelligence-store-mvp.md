# Sprint 5 Spec: Intelligence Store MVP

## Purpose

Add the first access-controlled Intelligence Store workflow. Sprint 5 lets
authorised product teams add existing mock products with rich metadata and asset
metadata, assign ACGs, search permitted products, inspect product details and
request controlled asset access.

The implementation remains local-first. It stores metadata and controlled
download tokens only, not real product bytes.

## Scope

- Product, asset and metadata domain records for existing products.
- API routes for product search, product detail, product creation, metadata
  suggestions and controlled asset access.
- Access filtering by RBAC, active ACG membership, clearance, status, product
  type, region, tags, project and source type.
- Product upload wizard UI with ACG assignment and asset metadata entry.
- Store search page with filters, safe result counts and product detail view.
- Regression tests for unauthorised search/detail/asset access and count leakage.

## Non-goals

- Real file upload, object storage streaming or signed cloud URLs.
- pgvector-backed semantic search. Sprint 5 uses deterministic local hybrid
  scoring while preserving a replaceable search service boundary.
- Persistent database tables and migrations.
- QC-driven automatic ingestion. The service boundary is prepared for it, but
  workflow integration remains later work.
- Synthetic bulk product generation. That starts in Sprint 6.

## Access Rules

- `product:read` is required to search and view product details.
- `product:create_existing` plus the relevant team permission is required to add
  existing products unless the actor has `system:configure`.
- Users only see products whose active ACGs intersect their active ACG
  memberships, unless they have `product:read_restricted`.
- Draft products require `product:manage_assets`; archived products are hidden
  from default search unless requested by administrators.
- Asset access is controlled through the API and re-checks product access before
  returning a placeholder download token.

## Acceptance Criteria

- Administrators can add existing products with metadata, ACGs and one or more
  assets.
- RFA and collection product roles can add products only within active ACGs they
  belong to.
- Required metadata and at least one ACG are enforced before publication.
- Each asset records name, MIME type, size, SHA-256 hash and object key.
- Metadata suggestions propose tags and entities but never auto-assign ACGs.
- Search returns only authorised products and does not leak unauthorised counts
  or facets.
- Filters work for product type, region, tags, project, source type and status.
- Product detail shows metadata and asset previews for authorised users.
- Controlled asset access succeeds only for authorised users.
