# Coeus Development Story: 2026-07-18

## Customer-controlled search and autonomous JIOC routing

- Kept the existing Gemini-capable hybrid retrieval, pgvector, chunking and
  citation stack. Added fixed release gates and a deployment allowlist instead
  of replacing a retrieval system that already performs well on the versioned
  synthetic relevance corpus.
- Made submission start bounded discovery automatically. Each run now persists
  independent outcome, assurance, coverage, corpus and provider provenance, so
  degraded or partial zero-result searches stop in an explicit retry state.
- Made Intelligence Store candidates customer decisions. The owner must accept
  a product as answering the request or reject it before the workflow can move
  on. Product rejection is never treated as consent for new collection or
  assessment work.
- Added authorised discovery across active RFIs, RFAs and collection
  requirements. Customers can join a canonical work item through a durable,
  idempotent subscription without acquiring broader access to its content.
- Unified the owner-only no-answer decision. Declining new tasking closes the
  request as unanswered; approving it creates a versioned JIOC routing context.
- Added a schema-constrained JIOC Routing Agent with deterministic evidence,
  transition and confidence policy. Routine RFA or CM decisions apply
  automatically; ambiguity, stale evidence, restrictions and low confidence
  fail closed to clarification or manager review.
- Kept the JIOC Manager on the loop through aggregate oversight and audited
  hold, resume and send-to-review interventions. Customers receive a separate
  safe stage, next-step and provisional ETA projection.
- Preserved collection-to-analysis context as explicit handoffs. QC now records
  deterministic structural and evidence-readiness preflight, while release
  still requires a current human QC claim and approval.
- Added independent rollback flags for automatic discovery, active-work offers
  and autonomous JIOC routing. Added regression coverage for disabled flags,
  incomplete searches, hidden work, ownership, idempotency, concurrency,
  intervention, agent abstention, preflight and customer-safe projection.

## Verification

- Backend: 1,176 passed and one intentional N-1 compatibility skip, including
  isolated PostgreSQL migration, transaction and concurrency tests. Coverage is
  98.09 per cent line and 95.12 per cent branch.
- Frontend: 518 passed at 98.85 per cent line and 95.05 per cent branch.
- Ruff, mypy, ESLint, TypeScript, Prettier, production build, architecture,
  documentation, security-policy, OpenAPI compatibility, dead-code and
  350-line-limit gates pass.

## Externally authored product, QC and customer outcome lifecycle

- Replaced metadata-only analyst drafts with ticket-scoped upload of real Word,
  PowerPoint, PDF and image products. Every version retains its original bytes,
  SHA-256, detected type, immutable metadata, ACGs and canonical manifest.
- Added bounded signature and Office-container inspection, exact-byte protected
  workflow preview, extraction for PDF, DOCX and PPTX, and fail-closed hosted
  malware-scanner policy. Unsafe, mismatched, malformed and active-content
  files are rejected before persistence.
- Pinned manager approval and QC ingestion to the immutable manifest. QC now
  shows the controlled product beside extracted text and structured
  UK-English spelling or duplicated-word findings. Image-only products carry a
  visible proofing-coverage warning because trusted OCR is not yet available.
- Promoted the approved original bytes into the Intelligence Store and added
  ACG-authorised inline preview. Office products use extracted-text fallback
  until a sanitised rendition worker is deployed; PDF and raster products can
  render inline.
- Added explicit customer acceptance and rejection. Acceptance closes as
  requirement met. Rejection requires a reason and returns to the responsible
  RFA or CM manager, who may order re-analysis or refer disagreement to an
  independent JIOC human for the final re-analyse-or-close decision.
- Added role-specific analyst, QC, customer, manager and JIOC controls, safe
  decision context, deterministic state transitions, separation of duties and
  optimistic audited persistence.

## External product lifecycle verification

- Backend: 1,206 passed, one intentional N-1 compatibility skip and 97.12 per
  cent combined coverage with all 70 PostgreSQL migration, codec, concurrency,
  transaction, outbox, reconciliation and projection tests passing.
- Frontend: the complete suite passed at 98.29 per cent lines/statements,
  95.04 per cent functions and 95.00 per cent branches.
- Focused security and behaviour cases cover file spoofing, macro and external
  relationship rejection, malformed archives, malware fail-closed behaviour,
  upload bounds, metadata validation, proofing coverage, exact-byte release,
  customer outcomes and both escalation branches.
- OpenAPI generation, Ruff, backend formatting, mypy, ESLint, Prettier,
  TypeScript, architecture, documentation, security-policy and file-line gates
  passed.

## Quality, maintainability and secure-by-design remediation

- Reproduced and closed four reportable security findings: stale identity
  overwrite during password change, unbounded retained sessions, cross-route
  manager draft disclosure and administrator draft disclosure. Current-state
  confirmation and one exact-object draft policy now own those boundaries.
- Repaired lower-severity but real upload, Office archive, XML, Windows restore
  and registration-oracle weaknesses before any supported deployment expansion.
- Removed obsolete production code and enabled development Knip, production
  Knip and Python declaration checks. One last coverage review found the old
  customer join service still present after the active-work migration; it was
  deleted and its live replacement remains fully exercised.
- Reduced service coupling by moving FastAPI composition to the API layer,
  introducing narrow read ports and injected provider callables, and enforcing
  the direction with an architecture gate. C901 now prevents complexity debt
  from silently returning.
- Made frontend route access, query identity and generated API contracts
  authoritative. Protected Blob URLs are short-lived, conflicts reconcile with
  the server, large-payload failures preserve drafts, and background refresh no
  longer overwrites dirty intake.

## Final remediation verification

- Backend: 1,233 passed and one intentional external N-1 source-tree skip,
  including PostgreSQL migration, transaction, concurrency, restore, codec,
  outbox and projection tests. Coverage is 98.13 per cent line and 95.15 per
  cent branch.
- Frontend: 530 passed at 98.65 per cent line, 95.05 per cent function and
  95.14 per cent branch coverage.
- Formatting, lint, strict typing, architecture, complexity, line-limit,
  contracts, documentation, security policy and both dead-code modes pass.
  Dependency audits found no known vulnerability. Bandit and redacted Gitleaks
  scans are clean.
