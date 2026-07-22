# Follow-up security scan remediation, 2026-07-22

## Goal

Remediate all 11 findings from sealed standard scan
`5af0222d-05d1-4c46-a090-018aff45db2d` without removing supported workflows or
changing successful API response shapes. The scan inspected the working-tree
snapshot based on revision `d1adc99fa6dc5585975c9fdd68a2bea551d2a769`, with
snapshot digest
`codex-security-snapshot/v1:sha256:bc926c3ab1103b23c1eb348339631941adcce2d1e0bcb045c0367f23c6cf3ea6`.
It reported three Medium and eight Low findings.

This follows the separate
[15-finding remediation](security-scan-remediation-2026-07-21.md). A complete
clean-revision scan is still required before production-release closure.

## Security invariants

- Administrator role, clearance and account-status changes atomically validate
  the current actor and target under one authority boundary.
- Ticket creation, active-work discovery, RFI search, intake chat and QC release
  carry an exact expected live `UserAccount` and the required permission to the
  final commit owner.
- Interactive chat, active-work discovery, RFI search and QC release also bind
  the exact initiating session. A different surviving session cannot authorise
  work begun by a session revoked while the request was in flight.
- PostgreSQL locks the relevant users row inside the committing transaction.
  Local persistence uses the same `authority_guard` semantics, while alternate
  compositions that cannot prove live authority fail closed.
- RFI commit confirms the requester still has an active ACG, then locks and
  revalidates the union of every offered product ID and every grounded-evidence
  product ID persisted by the result. QC release confirms current QC-team
  membership, draft access, release ACG authority and recipient visibility
  before publication.
- Protected workflow and submission locks follow one order: users, sessions,
  access, teams, products, then ticket. Active-work results and their audit
  event commit as one guarded unit.
- QC publication, indexing, dissemination and audit effects occur only inside
  guarded confirmation of current reviewer and release authority.
- Provider JSON deeper than 32 levels fails through deterministic fallback and
  counts exactly once towards provider circuit state.
- PDF extraction permits at most 1,000,000 decoded bytes per content or Form
  stream, 8,000,000 per document, 2,048 stream invocations, 2,048 Form
  invocations, 100,000 operations and Form depth 32. It safely accounts for
  inherited resources, resource-free content, repeated Forms and cyclic Forms.
- DOCX preflight permits at most 1,024 logical cells in one row and 10,000 in
  one document, XML depth 64 and 50,000 work units before `python-docx`
  materialises the table model.
- Analyst PDF and DOCX parsing runs through `asyncio.to_thread`, keeping
  synchronous third-party parsing off the API event loop.
- Staging and multipart context exit are cancellation-safe. A cancelled product
  submission retains its admission reservation and staged file until the parser
  thread exits, then releases and removes them without partial publication.

## Compatibility requirements

- Current administrators retain supported role, clearance and status controls.
- Authorised users retain ticket creation, chat, active-work and RFI search
  behaviour, including current conflict and error response shapes.
- Current QC reviewers retain the human-controlled publish and dissemination
  journey when their authority remains valid through commit.
- Valid provider plans at or below the depth limit keep the existing structured
  result contract; invalid or excessive results use the existing safe fallback.
- Valid PDFs and DOCX files within the declared semantic budgets retain their
  extracted text, product submission and indexing workflows.
- Revoked, disabled or stale actors receive a non-disclosing rejection without
  protected state, product, index, audit or outbox residue.
- Cancelling upload staging, multipart exit or document submission leaves no
  durable product or orphaned staging file and does not release admission while
  a parser thread can still access the file.

## Acceptance criteria

- Deterministic barriers prove revocation wins before each of the eight protected
  mutation families commits, with a positive current-authority control through
  the same boundary.
- PostgreSQL, local and fail-closed alternate composition tests prove equivalent
  authority semantics and the users, sessions, access, teams, products, ticket
  lock order.
- Revoking only the initiating session denies chat, active-work, RFI and QC
  release commit even when the same user retains another session. Restoring the
  exact initiating session provides the positive compatibility control.
- RFI regression tests deny a requester with no active ACG or any newly hidden
  offered or non-offered grounded-evidence product. Active-work tests prove
  result and audit atomicity.
- QC regressions deny stale team membership, draft access, release ACG authority
  or recipient visibility before any publication side effect.
- QC publication is impossible unless guarded authority confirmation succeeds
  inside the release transaction.
- Nested JSON at depth 32 succeeds when valid; depth 33 fails safely, activates
  fallback and records the provider failure once.
- PDF per-stream, per-document, stream-invocation, Form-invocation, operation and
  Form-depth boundaries have at-limit and over-limit controls, including
  inherited, resource-free, repeated, nested and cyclic inputs.
- DOCX row and document cell budgets reject hostile `w:gridSpan` geometry before
  `python-docx` parsing. XML depth 64 and 50,000 work-unit limits have positive
  and over-limit controls alongside valid merged tables.
- A concurrent lightweight request remains responsive while analyst document
  parsing executes through bounded thread admission.
- Cancellation tests cover staging, multipart context exit and submission while
  preserving admission and staged-file lifetime until the parser exits.
- Backend and frontend application line and branch coverage remain at least
  95 per cent, and repository formatting, linting, typing, architecture,
  contracts, documentation, security and line-limit gates pass.

## Focused implementation evidence

- Administrator authority regressions: 17 passed.
- Workflow authority regressions: 99 local and four real PostgreSQL tests passed,
  including initiating-session, visibility, lock-order and atomic-audit cases.
- The combined real-PostgreSQL lock-order suite passed 5/5 after
  workflow and submission paths adopted the canonical order. It includes QC
  initiating-session deletion denial and a restored-session positive control.
- The expanded local focused compatibility suite passed 77/77, including QC
  initiating-session and non-offered RFI evidence-product races.
- Parser and cancellation regressions: 124 broader tests passed.
- Submission-race regressions: five passed.
- Product and indexing regressions: 31 passed.
- Parser-service coverage: 98.53 per cent. Upload-route coverage: 95.92 per cent.
- Python and pnpm dependency audits reported no known vulnerabilities.
- Ruff, mypy, line-limit and diff-focused checks passed.

Full PostgreSQL-backed verification passed 1,606 tests with one intentional
compatibility skip at 98.23 per cent line and 95.33 per cent branch coverage.
The 537-test frontend suite passed at 98.63/95.03 per cent line/branch coverage.
A fresh sealed scan of a clean resulting revision remains required before
release-candidate status is claimed.
