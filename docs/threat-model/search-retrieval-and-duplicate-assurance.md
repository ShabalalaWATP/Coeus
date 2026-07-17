# Threat Model: Search Retrieval and Duplicate Assurance

## Scope

Sprint 20 search administration, document extraction, chunk indexing, embedding
providers, cited RFI results, relevance evaluation and full-corpus similar RFI
and RFA discovery.

## Assets

- Intelligence product metadata, document text, chunks and citations.
- Derived embeddings, model provenance, corpus version and index status.
- Ticket intake text, route, team, operation and similarity relationships.
- ACG membership, clearance and object-level visibility decisions.
- Search provider credentials and externally transmitted content.
- Audit evidence for configuration, re-index and duplicate actions.

## Trust Boundaries

- Browser to administrator API.
- Application to encrypted configuration persistence.
- Application to local object storage and hostile document parsers.
- Application to PostgreSQL full-text and pgvector indexes.
- Application to an explicitly selected external embedding provider.
- Search result serialisation back to the requesting user or manager.

## Threats and Controls

| Threat | Control |
|---|---|
| A chunk or citation leaks a product outside the requester's ACG or clearance. | Both retrieval legs join the chunk to its parent product and apply status, mock-release, clearance and ACG predicates before ranking. Results are reauthorised during serialisation. |
| Vector nearest-neighbour search considers hidden rows before filtering. | Access predicates are inside each lexical and vector candidate query. A post-filter-only query is prohibited and covered by SQL and PostgreSQL tests. |
| A model switch compares incompatible vector spaces. | Provider, model, dimensions and generation must match the active configuration. Configuration changes disable vector retrieval until a complete compatible generation is promoted. Corpus-only staleness may reuse that same generation solely as a labelled degraded leg alongside complete lexical coverage. |
| A partial or failed re-index becomes active. | Re-index writes a new generation and promotes it only after all eligible products complete. Failure preserves the previous ready generation or lexical-only mode. |
| An administrator accidentally sends sensitive text to a cloud provider. | Fresh installs remain offline. The external provider requires a saved key, explicit activation and a data-boundary confirmation, and Admin offers a connection test first. The event is audited. |
| Search API keys are disclosed or tampered with. | Keys use the encrypted integration secret store, are write-only in the API, never logged, and fail closed on decryption or integrity errors. Environment-managed keys cannot be replaced in Admin. |
| A malicious PDF or DOCX executes code, fetches a URL or exhausts resources. | Extraction uses non-executing parsers, never enables macros or external resources, and enforces byte, page, character, chunk, concurrency and time budgets. Malformed assets produce bounded warnings. |
| Extracted text introduces stored XSS or terminal/control-code injection. | Text is normalised, control characters are removed, excerpts are length bounded and React renders them as escaped text. |
| Chunk text or provider errors enter logs. | Structured logs contain identifiers, counts and fixed reason codes only. Raw document, query, key and upstream exception bodies are excluded. |
| Degraded lexical search is mistaken for a definitive no-match. | Retrieval mode is persisted and returned. A lexical-only zero result cannot trigger the same definitive no-match presentation as a healthy hybrid run. |
| A newly submitted ticket is missed or down-ranked because the last generation lacks its vector. | Similar-request lexical scoring always covers the complete authorised corpus. Fusion is normalised per candidate, and a weak or absent vector leg cannot reduce a strong lexical match. |
| Citation text is unrelated to the offer. | Passages must come from the selected product and carry stable asset/page provenance. The evaluation checks citation-product identity and lexical or vector support. |
| Re-index can be abused for denial of service or excessive provider spend. | The endpoint requires `SYSTEM_CONFIGURE`, CSRF validation, provider admission, one active job, bounded batches and an audit event. Repeated starts are idempotent or rejected. |
| Similar-request search becomes a hidden-ticket existence oracle. | Customer retrieval still sees only tickets already visible to the customer and returns no count, flag, timing distinction or audit event derived from hidden tickets. |
| A broad manager permission reveals an unauthorised workflow corpus. | The source and every returned match require the existing workflow object scope. Route, team and operation are returned only after that check. |
| Marking a duplicate silently cancels work or loses history. | The action is manager-only, state constrained, reciprocal, transactional and audited. It does not merge history, grant access or withdraw released products. |
| Relevance metrics are inflated by inaccessible or generator-coupled examples. | Qrels are separate from corpus generation. Hidden products never count as retrieved, access leakage fails the run, and production claims require real PostgreSQL/provider execution. |

## Security Tests

- A permitted and a forbidden chunk with identical text prove pre-filtering.
- Changing model or generation proves incompatible vectors cannot affect rank
  or count. Corpus-only staleness proves matching-generation vectors remain
  labelled degraded and cannot authorise a definitive no-match.
- Failed and interrupted re-index runs prove no partial generation is promoted.
- Malformed, encrypted, oversized and high-page-count documents fail safely.
- API, logs, audit events and browser state contain no API key or raw provider
  exception.
- A lexical-only zero result includes its degraded mode and does not claim a
  complete search.
- A hidden similar ticket produces the identical customer response as no match.
- Duplicate action permission, invalid state, audit failure and stale-write
  tests prove transactional rollback.

## Residual Risks

- Embeddings are sensitive derived data and may permit membership inference.
  Database access, backups and exports must protect them like source content.
- Third-party document parsers can contain vulnerabilities. Dependencies require
  audit and prompt patching, and a future production deployment should isolate
  extraction in a sandboxed worker.
- External embedding quality and availability can change. The stored model ID,
  corpus version and evaluation result make that drift observable but cannot
  eliminate it.
- Search remains retrieval assistance, not an autonomous intelligence
  judgement. A human must review citations and product suitability.
