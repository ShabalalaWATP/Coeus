# Spec: Store Hybrid Browse Search

## Goal

Use the existing Store hybrid retrieval engine for Intelligence Store browse
searches that include free text, while preserving the current no-query browse
experience for structured filtering, facets and pagination.

## Behaviour

Store search has two paths:

- **No free-text query:** keep the existing browse path. Products are scoped by
  ACG, clearance, draft visibility and archive state, filtered by structured
  fields, sorted by title and paginated exactly.
- **Free-text query:** build one query embedding through the configured
  `EmbeddingService`, retrieve hybrid candidates from the existing Store
  projection path, then return the same `StoreSearchResult` shape with ranked
  hits, scores and match reasons.

The free-text path must continue to apply `product_type`, `source_type`,
`status`, `project_id`, `owner_team`, `region`, `tag` and coverage date filters
before ranking. The query itself narrows the result set, but structured facets
are computed from the access-scoped set after only structured filters are
applied.

## Pagination And Totals

`total` and `total_pages` describe the full access-scoped, structured-filtered
and text-matched result set, not only the returned page. The implementation may
use a large internal candidate cap for the current local Store size, but the
cap must not be the public page size and must be documented in code.

## Relevance And Reasons

Default query order is server relevance order. Hybrid candidates expose:

- lexical rank;
- vector similarity when available;
- metadata and semantic label reasons;
- `retrieval:lexical-only` when the embedding provider cannot produce a query
  vector or no vector leg contributes.

`match_score` and `match_reasons` are returned on every Store search hit. The
frontend shows a compact reason hint when a text query is active.

## Degradation

Embedding provider selection remains authoritative. The default provider is
`mock` and is fully offline. `local` and `gemini_api` are used only when
explicitly configured. If the selected provider cannot embed the query, browse
search must not fail. It falls back to lexical retrieval and records
`retrieval:lexical-only` in result reasons.

## Access Invariants

- ACG membership, clearance, draft visibility and archived-product predicates
  are applied before ranking.
- The service layer rechecks `can_read` before returning results.
- Hidden products must not affect ranks, counts, facets or reasons.
- The in-memory fallback must apply the same structured filters as the
  PostgreSQL projection path.

## Acceptance Criteria

- Word-order queries such as `vessel port` and `baltic maritime` can return a
  product whose metadata contains both terms non-contiguously.
- Stemmed or related terms can match through PostgreSQL full text, semantic
  labels or the configured embedding provider.
- A cross-word-boundary substring such as `port vessel` does not match only
  because it appears inside adjacent words.
- Facets remain populated from the structurally-filtered scoped set, not only
  the text-matched subset.
- Pagination and totals are exact for the returned query result set.
- Provider-degraded browse search returns lexical results rather than an error.
