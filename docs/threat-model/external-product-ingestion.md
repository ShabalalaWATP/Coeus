# Threat Model: External Product Ingestion

## Scope

Ticket-scoped DOCX, PPTX, PDF and image upload; extraction and preview; automated
proofing; manager and QC review; Store release; customer acceptance; and
re-analysis adjudication.

All repository examples and tests use synthetic data only.

Companion records: [feature contract](../specs/external-product-ingestion-and-customer-acceptance.md)
and [ADR 0037](../adr/0037-ticket-scoped-external-product-lifecycle.md).

## Assets And Trust Boundaries

- Analyst source bytes and immutable hashes.
- Product metadata, ACGs, classification and release controls.
- Extracted text, preview renditions and QC findings.
- Customer, manager and JIOC decisions.
- Workflow object storage, background processing, relational projections and
  the browser rendering boundary.

Client filenames, MIME types, Office/PDF contents, extracted text and QC model
output are untrusted. Identity, active assignment, live ACG membership and
server-generated hashes are trusted only after server-side verification.

## Threats And Controls

### Malicious or misleading files

- Enforce a cumulative receive-time body limit before multipart spooling,
  including bodies without `Content-Length`.
- Detect file type from magic bytes and structural validation, not extensions.
- Reject macro-enabled, encrypted, malformed and unsupported containers.
- Validate ZIP member count and total expanded size before building name sets;
  read relationship and slide XML through per-member expanded-byte limits;
  reject DTDs and entities with a hardened XML parser before text extraction.
  Bound extracted characters, images and processing time as later controls.
- Production conversion runs in a non-networked, read-only, resource-limited
  worker with patched parsers and malware scanning.

### Active content and preview compromise

- Never render raw Office HTML or execute macros, scripts, links or embedded
  objects.
- Render only sanitised PDF or raster derivatives in a sandboxed, separate
  response context with restrictive content type and `no-store` caching.
- Bind preview grants to user, ticket, submission, asset and short expiry.
- Re-authorise every grant and byte response against live workflow or Store
  policy.

### Broken object-level authorisation

- Upload and source preview require the exact active analyst assignment,
  responsible same-route area manager or named QC reviewer at the applicable
  state. Every byte sink, including QC auto-ingestion, calls the shared live
  ticket/version policy before object storage. Platform administration,
  `TICKET_READ_ALL` and global `PRODUCT_APPROVE` alone grant no draft access.
- Store access continues to require active user, clearance, status and ACG
  intersection. Identifiers alone confer no access.
- Queue summaries disclose no filenames, extracted text or findings before a
  reviewer claims the item.

### Release of different bytes

- Finalisation freezes metadata and asset identities.
- Manager approval, QC run and release all reference the same version and
  canonical hash.
- Release re-reads source bytes, verifies size and SHA-256, writes the Store
  copy, verifies it, then publishes through the workflow transaction.
- Compensation deletes only failed Store copies, never the source submission.

### Prompt injection and unreliable proofing

- Delimit extracted document text as untrusted data and exclude tool authority.
- Require structured, schema-validated findings with policy/model versions.
- Deterministic file integrity, access, release and state rules are never
  delegated to a model.
- Human QC sees the original context and decides every finding and release.
- Model failure, low confidence or extraction limits are visible and fail safe.
- Raster images without trusted OCR produce an explicit proofing-coverage
  finding and remain subject to human review.

### Workflow abuse and race conditions

- Customer decisions are owner-only and require the current released version.
- Manager agreement/disagreement is route-scoped and requires rationale.
- JIOC final action uses a dedicated permission and cannot be performed by the
  analyst, customer or deciding team manager.
- Optimistic compare-and-swap makes duplicate or stale decisions conflict.
- Every transition records actor, old/new state, product/version and reason.

### Information leakage through processing

- No public cloud viewer, external spelling API or telemetry receives content.
- Logs contain identifiers and result codes, not source text, tokens or bytes.
- Temporary files are private, bounded and deleted on success and failure.
- Derived artefacts inherit source classification and ACGs.

## Verification

- File-signature spoofing, malformed ZIP/XML, macro and size-limit tests.
- Cross-ticket, unassigned, stale-role and revoked-ACG access tests.
- Hash preservation and release rollback tests.
- Preview token replay and cache-header tests.
- Prompt-injection corpus and deterministic finding tests.
- Full customer rejection, manager decision and both JIOC branches.
- PostgreSQL concurrency tests for upload finalisation and every decision.
