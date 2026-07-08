# ADR 0017: Store Browse Uses Hybrid Search

## Status

Accepted

## Context

The RFI Search Agent already uses Store hybrid retrieval: PostgreSQL full text,
pgvector cosine similarity and Reciprocal Rank Fusion inside ACG and clearance
predicates. The Intelligence Store browse page used a separate substring-based
filter, so multi-term queries depended on word order and results were often
alphabetical rather than relevance-ranked.

Running two search behaviours makes the product harder to reason about and
risks users seeing weaker Store results than the agent uses.

## Decision

Route Store browse requests with a non-empty free-text query through the
existing hybrid candidate engine. Empty-query browse keeps the existing
structured filter, facet and title-ordered pagination path.

The backend keeps one public response shape. Query results are converted into
`StoreSearchHit` records with score and reasons from the hybrid candidate.
Facets are computed from the access-scoped set after structured filters only,
so users can still see useful refinement options after a narrow query.

Browse uses the same token-boundary lexical scorer as RFI and similar-request
matching, including conservative singular and plural folding. It does not use
cross-word substring matching. A query result must be present in the lexical
leg or meet the shared vector similarity floor before it is returned. Semantic
label and metadata reasons explain selected hits only; they are not membership
signals.

The browse candidate window is intentionally larger than RFI search: 500
candidates per lexical or vector leg for Store browse, and 50 per leg for RFI
offer generation. The larger Store window supports exact browse totals and
pagination for the current local catalogue size without changing RFI scoring.

Provider selection remains explicit. The default mock embedding provider stays
offline and deterministic. If the configured provider cannot return a vector,
the Store search degrades to lexical-only retrieval rather than failing.

The in-memory fallback computes product vectors on demand using the configured
embedding provider and purpose `memory-candidate`. That cost is accepted for
local development and CI, where the default mock provider is offline and cheap.
Non-mock providers should use the PostgreSQL projection path so product
embeddings are stored and reused.

## Rejected Alternatives

- **A second browse search index:** rejected because it would duplicate ranking
  logic and create another place to enforce need-to-know filtering.
- **Always using hybrid retrieval, even without text:** rejected because empty
  browse is a catalogue/filter workflow where exact totals, facets and stable
  title ordering are more useful than relevance scores.
- **Client-side semantic ranking:** rejected because access control and
  relevance counts must be enforced server-side.

## Consequences

- Store users and the RFI Search Agent now share the same retrieval semantics
  for free-text product discovery.
- The Store browse API depends on the configured embedding service for query
  searches, but still works when embeddings are unavailable.
- Facet semantics are explicit: they describe structured availability, not only
  the current text-matched subset.
- Existing product semantic hashes do not change because label vocabularies are
  not injected into product semantic text. Re-embedding is not required for this
  browse change.
