# Spec: Search Retrieval and Duplicate Assurance

## Status

Sprint 20 implementation contract.

## Goal

Make Intelligence Store search evidence-grounded and make in-progress RFI and
RFA discovery dependable at the full authorised corpus size. Search must expose
its operating mode, cite the exact product passages that support a result and
never compare vectors produced by incompatible embedding configurations.

## Scope

- A dedicated Admin **Search and embeddings** control plane, separate from text
  chat and Realtime voice settings.
- Persisted embedding provider, model and dimensionality, with an encrypted API
  key reference, index status, corpus version and an explicit re-index action.
- Local extraction of bounded PDF and DOCX content into page-aware chunks.
- Access-filtered lexical and vector retrieval over product metadata and chunks.
- Field-weighted RFI retrieval using question, context, region, operation,
  discipline, output format, time window, urgency and requesting unit.
- Visible degraded-mode reporting when semantic retrieval is unavailable.
- Full-corpus similar-request retrieval for active RFI, RFA and collection work.
- Manager match details and controlled link, duplicate and withdrawal actions.
- A labelled, synthetic relevance evaluation with release-blocking metrics.

## Embedding Configuration

The quality-first production recommendation is:

| Setting | Value |
|---|---|
| Provider | `gemini_api` |
| Model | `gemini-embedding-2` |
| Output dimensions | `1536` |
| Distance | cosine |

`gemini-embedding-2` is selected because Coeus already has a separately
managed Gemini credential, the model supports text and document retrieval in a
shared multilingual embedding space, and 1,536 dimensions fit pgvector's
full-precision HNSW `vector` limit. The 3,072-dimension option is not selected
because it would require half-precision storage or exact search for HNSW. A
large self-hosted model is not selected as the application default because it
would make the supported desktop runtime materially heavier.

The selected quality model is not an implicit runtime default. Fresh local and
CI environments remain on `mock`, use no network and work without cloud access.
An administrator must save a Gemini credential, explicitly confirm the egress
boundary, activate the search configuration and start a re-index before corpus
embedding calls occur. Admin also provides a connection test before activation.

## Index Identity and Lifecycle

Every search chunk and active-ticket vector is associated with a generation
profile that records:

- provider;
- model;
- output dimensions;
- source-content hash;
- index generation;
- generation creation and completion timestamps.

The vector row itself records its source-content hash and joins to that profile
by generation. The legacy 384-dimension product vector remains a separate
compatibility projection and is never compared with this search index.

The active index identity is
`provider:model:dimensions:generation`. Retrieval uses a vector only when all
identity fields match the active configuration. A provider, model or dimension
change creates a new generation and immediately marks the semantic index
`stale`. Mixed-space comparisons are prohibited. When only the corpus has
changed, the last complete matching-generation vectors may still contribute as
a degraded semantic leg alongside full-corpus lexical retrieval. This preserves
useful ranking for a newly submitted RFI without pretending the generation is
complete or allowing a definitive zero-result decision.

Index states are `ready`, `stale`, `indexing`, `degraded` and `failed`. State
includes product count, chunk count, last successful completion, bounded error
summary and corpus version. Re-indexing is idempotent and auditable. Only one
re-index can run at a time. A failed re-index retains lexical search and does
not promote a partial generation to `ready`.

## Document Extraction and Chunking

Extraction occurs locally before any text is embedded. Supported formats are:

- PDF, one page at a time;
- DOCX, using document order and a synthetic page number when no real page
  boundary exists;
- existing product metadata as a page-zero evidence record.

The extraction boundary is deliberately bounded:

- no macros, external links, network fetches or embedded-object execution;
- at most 200 pages and 2,000,000 extracted characters per asset;
- at most 500 chunks per asset;
- normalised text chunks of approximately 900 words with 120-word overlap;
- empty, encrypted, malformed or unsupported assets produce an indexed warning,
  not an application crash;
- raw extracted text is not written to logs.

Each chunk stores product ID, asset ID, asset name, page number, chunk ordinal,
content, content hash, lexical document and embedding provenance. Product ACG,
clearance, status and mock-release policy remain authoritative through a join
to the parent product before a chunk can be ranked, counted or returned.

## RFI Retrieval

RFI search builds separate field groups rather than one concatenated string:

| Field group | Relative weight |
|---|---:|
| Operational question and description | 1.00 |
| Known context and success criteria | 0.75 |
| Area or region and supported operation | 0.65 |
| Intelligence disciplines and output format | 0.45 |
| Requesting unit, restrictions and urgency | 0.25 |

The lexical and vector legs retrieve authorised product metadata and chunks.
Ranking then combines absolute evidence with:

- requested-versus-product time-window overlap;
- freshness relative to the requested end date;
- region overlap;
- supported-operation overlap;
- discipline and output-format overlap;
- a penalty for non-overlapping dated products;
- a bounded reciprocal-rank ordering signal.

The response returns at most five product offers. Each offer can contain up to
three evidence passages. A passage includes a bounded excerpt, asset name,
page number and stable citation label. A product without a supporting passage
may be offered from strong metadata evidence, but is labelled
`metadata-only`. Coeus does not synthesise a free-text intelligence answer in
this sprint. It returns the grounded evidence needed for a reviewer to decide.

## Retrieval Mode and Abstention

Every run records and returns one of:

- `hybrid`, when lexical and matching-generation vector evidence were used;
- `lexical_only`, when vectors were unavailable, incompatible or had no usable
  candidates;
- `metadata_only`, when no searchable document content exists.

The response includes a safe public explanation and an admin-visible reason.
A lexical-only zero result does not become a definitive product no-match. The
ticket remains reviewable and the customer is told that semantic retrieval was
unavailable. No provider exception text is exposed.

## Similar RFI and RFA Discovery

Similarity covers `INFO_REQUIRED`, `RFI_SEARCHING`, `RFI_MATCH_OFFERED`,
`RFI_NO_MATCH`, `JIOC_REVIEW`, `COLLECT_CHOICE`, `ANALYST_ASSIGNMENT`,
`ANALYST_IN_PROGRESS`, `MANAGER_APPROVAL`, `QC_REVIEW`, `REWORK_REQUIRED` and
`DISSEMINATION_READY`.

PostgreSQL performs access and state filtering before full-corpus lexical and
vector top-K retrieval. There is no arbitrary first-100 candidate truncation
and no lexical precondition before semantic comparison. Memory persistence uses
the same scoring contract over its complete bounded local corpus.

Reciprocal-rank and absolute signals are normalised per candidate. A ticket
created after the last generation can therefore remain a strong lexical match,
and adding a weak semantic leg cannot reduce a strong lexical match below the
customer or manager threshold.

Manager results include reference, title, state, approved route, assigned team,
requested time window, operation, score, reasons and whether the pair is linked
or already marked duplicate. Customer responses retain the existing zero-signal
rule for invisible tickets.

Controlled manager actions are:

- link as related, idempotently;
- mark the source as a duplicate of the selected target, recording reciprocal
  linkage and an audit event;
- withdraw the duplicate source only when its current state permits
  cancellation and no released product would be hidden.

No action merges ticket history, silently changes ownership or grants access to
the target. Cross-visibility collaboration remains a separate authorised act.

## Relevance Evaluation

The repository contains versioned synthetic queries and graded relevance
judgements, separate from the corpus generator. The set covers:

- domain synonyms and acronyms;
- spelling and speech-transcription errors;
- UK dates and non-overlapping date hard negatives;
- geographic aliases and ambiguous regions;
- sparse and long questions;
- negation and no-match cases;
- route-aware RFI and RFA duplicates;
- restricted products that must never affect a metric.

Release gates on the held-out set are:

- access leakage: exactly zero;
- Recall@5: at least `0.90`;
- Precision@5: at least `0.70`;
- nDCG@5: at least `0.85`;
- no-match false-offer rate: at most `0.10`;
- degraded-mode identification: `1.00`.

The deterministic synthetic set verifies scoring, abstention, access and
degraded-mode mechanics. Separate PostgreSQL/pgvector tests verify the real SQL
prefiltering and hybrid-retrieval path. Before a production provider is
approved for deployment, the same held-out set must be run with that provider;
mock results are never described as proof of its semantic quality.

## Security Invariants

- Access predicates execute before metadata, chunk or vector ranking.
- Citations are authorised again when results are serialised.
- Product and ticket text leaves the application only after explicit external
  provider activation and only for the configured embedding purpose.
- Search credentials are encrypted at rest and never returned, logged or placed
  in generic configuration payloads.
- Index generation prevents mixed embedding spaces from being used. A
  corpus-stale matching generation is labelled degraded and is combined only
  with complete lexical coverage.
- Re-index is administrator-only, CSRF-protected, admission-controlled, audited
  and single-flight.
- Extraction treats every document as hostile data and never executes content.
- Errors and metrics do not reveal hidden products, chunks, tickets or counts.

## Acceptance Criteria

- A query whose answer appears only in an authorised PDF or DOCX passage returns
  that passage with the correct product, asset and page citation.
- A time-window hard negative ranks below a genuinely overlapping product.
- Switching embedding model marks the index stale and prevents old vectors
  being compared with new query vectors.
- Submitting a new request after indexing still uses the matching-generation
  product vectors, finds a strong lexical-only new-ticket duplicate and cannot
  turn a degraded zero result into a definitive no-match.
- A failed provider visibly returns `lexical_only` and cannot produce an
  unqualified no-match outcome.
- The Admin page persists search provider, model and key configuration across a
  restart and shows index progress and corpus version.
- A relevant active ticket placed after 100 unrelated tickets remains
  discoverable, including an RFA-routed and a collection-routed example.
- Manager matches show route, team, time window and operation, and duplicate
  withdrawal is transactional and audited.
- The labelled deterministic evaluation gates pass, and real PostgreSQL and
  pgvector integration tests prove access-prefiltered lexical/vector mechanics.
- A production-provider release remains blocked until its own held-out
  evaluation meets the same gates.
- Backend and frontend line and branch coverage remain at least 95 per cent and
  all repository quality and security gates pass.
