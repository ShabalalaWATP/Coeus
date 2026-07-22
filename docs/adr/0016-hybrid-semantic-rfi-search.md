# ADR 0016: Hybrid Semantic RFI Search

## Status

Accepted, superseded in part by the later retrieval-assurance implementation.
The current offer threshold is `0.20`, owned by `rfi_ranking.py`; `0.34` below
records the original decision.

## Context

The Sprint 7 RFI Search Agent was intentionally deterministic and local-first,
but it ranked products with token overlap only. PostgreSQL and pgvector now
exist in the local persistence stack, with an unused `vector(384)` column on
Store products. The next step is better retrieval without weakening the
need-to-know boundary.

## Decision

Use PostgreSQL as the single search boundary. Store products get a 384-dimension
embedding written to `intelligence_store_products.embedding`, indexed by HNSW
with `vector_cosine_ops`. RFI search retrieves top-50 lexical and top-50 vector
candidates inside the same status, clearance and ACG predicates, then fuses the
ranked lists with Reciprocal Rank Fusion using `k = 60`.

The vector leg applies the shared vector similarity floor before a product is
eligible. Lexical matching uses whole-token matching with conservative singular
and plural folding, not substring matching. Store browse reuses the same shared
token and fusion helpers but opts into a wider browse candidate window.

The embedding provider is selected by `COEUS_EMBEDDING_PROVIDER`:

- `mock`, the default, hashes canonical tokens into a deterministic
  384-dimension vector and never uses the network;
- `local` uses FastEmbed with `BAAI/bge-small-en-v1.5`, matching the existing
  `vector(384)` column and avoiding torch;
- `gemini_api` uses the configured Gemini API key and requests a 384-dimension
  embedding output.

Provider configuration is authoritative. Keys, installed models or optional
packages never switch the provider implicitly. If a non-mock provider is
unavailable, search falls back to lexical-only retrieval and logs a structured
warning without exposing secrets.

Scores are normalised to `0..1` after RRF. Metadata and controlled semantic
labels are retained as small tie-break bonuses. The original offer threshold was `0.34`,
which rejects weak single-leg tail matches but allows strong lexical or semantic
matches to be offered.

Product semantic text is built only from the product's own title, summary,
description, metadata, tags, labels and asset types. Label vocabularies help
derive labels and reasons, but they are not appended to the embedding or lexical
document text.

## Rejected Alternatives

- **Separate vector database:** rejected because it would duplicate access
  filtering and create a second place where hidden products could leak through
  nearest-neighbour search.
- **Torch-based sentence-transformers:** rejected for local defaults because it
  is heavier than needed for a desktop-first app and would slow CI and setup.
- **Implicit provider switching:** rejected because a stray API key or installed
  model should not send Store text to an external provider.

## Consequences

- Local and CI runs remain offline by default.
- PostgreSQL remains the only production search and access-control boundary.
- Store projection writes now depend on an embedding service, but product domain
  records and compatibility state payloads do not store vectors.
- Gemini embedding quality can be enabled explicitly later without changing the
  workflow contract.
