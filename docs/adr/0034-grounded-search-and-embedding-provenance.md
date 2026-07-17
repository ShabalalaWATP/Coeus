# ADR 0034: Grounded search and embedding provenance

## Status

Accepted for Sprint 20, 17 July 2026.

## Context

Coeus currently indexes product metadata into one `vector(384)` value and the
default provider is a deterministic token hash. Attached PDF and DOCX bodies
are not searched. Product vectors record only a source-text hash, so changing
provider or model can compare incompatible vectors. Similar-request discovery
also truncates the corpus before relevance ranking.

The application needs production-quality retrieval without weakening its local
offline runtime or its access-control boundary.

## Decision

Use `gemini-embedding-2` with 1,536 output dimensions as the recommended
quality-first embedding configuration for Coeus. Keep `mock` as the fresh local
and CI default. External search activation is always explicit.

The choice is architecture-specific rather than a claim that one public model
is universally best. It provides current multilingual and multimodal retrieval,
fits the existing Gemini credential boundary and keeps full-precision pgvector
HNSW storage because 1,536 dimensions are below pgvector's 2,000-dimension
`vector` index limit. The 3,072-dimension output is rejected because indexed
storage would require half precision. A large self-hosted embedding model is
rejected as the supported desktop default because of its runtime footprint.

Persist provider, model, dimensions, source hash and index generation beside
every product and chunk vector. Queries may use only vectors whose complete
identity matches the active configuration. Configuration changes create a new
generation and require explicit re-indexing. A complete generation that becomes
corpus-stale may remain a degraded semantic leg alongside full-corpus lexical
retrieval, because its vector space is still compatible. It cannot support a
definitive zero-result decision.

Extract bounded PDF and DOCX text locally into page-aware chunks. Store chunk
lexical documents and vectors in PostgreSQL, joining through the parent product
for status, clearance and ACG filtering before ranking. Keep product metadata
as page-zero evidence so unsupported documents remain searchable.

Use field-weighted hybrid retrieval, absolute lexical and cosine evidence,
temporal overlap, freshness, region, operation, discipline and format signals.
Return cited passages. Do not add free-text answer synthesis until citation
support and abstention have their own measured evaluation.

Move similar-request discovery to full-corpus database retrieval with the same
embedding provenance discipline. Preserve the customer zero-signal rule for
hidden tickets and expose richer details only to authorised managers.

## Rejected Alternatives

- **Continue metadata-only search:** rejected because a product can contain the
  answer without repeating it in metadata.
- **Use the selected chat or voice model for embeddings:** rejected because
  generation and retrieval models have different contracts and credentials.
- **Adopt 3,072 dimensions:** rejected because full-precision HNSW pgvector
  indexing does not support that width.
- **Use a separate vector database:** rejected because it would duplicate ACG
  and clearance policy and create another leakage boundary.
- **Implicitly re-use old vectors after model changes:** rejected because cosine
  scores across different embedding spaces are meaningless.
- **Generate a prose answer immediately:** rejected until passage retrieval,
  citation correctness and abstention are independently assured.

## Consequences

- PostgreSQL projections gain product provenance and page-aware chunk tables.
- Re-indexing becomes an explicit, observable administrative operation.
- External embedding activation sends authorised synthetic content to the
  configured provider and therefore requires a clear data-boundary warning.
- Lexical search remains available when embedding or indexing fails, but the UI
  must identify the degraded mode.
- Newly submitted requests do not disable compatible product vectors. Partial
  ticket-vector coverage is fused per candidate so a missing or weak semantic
  leg cannot suppress a strong lexical duplicate.
- Existing 384-dimension product vectors remain an isolated compatibility
  projection. They are not compared with, copied into or treated as evidence
  for the new 1,536-dimension generation index.
- Relevance metrics become release gates rather than informal demonstration
  evidence.

## References

- Google Gemini Embedding 2 model documentation:
  <https://ai.google.dev/gemini-api/docs/models/gemini-embedding-2>
- Google embeddings guide: <https://ai.google.dev/gemini-api/docs/embeddings>
- pgvector index limits: <https://github.com/pgvector/pgvector/blob/master/README.md>
