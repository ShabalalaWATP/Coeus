# Coeus Security Repair And Hardening Plan

## Status And Authority

Status: implementation in progress and release-blocking from 2026-07-13.

This plan is the implementation handoff for Sprint 17. It sits below the
authoritative root `coeus_spec_driven_implementation_plan.md` and must be kept in
step with `docs/MASTER_IMPLEMENTATION_PLAN.md` and `docs/DEVELOPMENT_STORY.md`.

The evidence baseline is the completed deep scan of immutable revision
`3e27c82d4b62efb683b3fbb81d2486bccafd8fb0`:

- scan ID: `abf0e143-4656-4646-b133-6fea0d6661ee`;
- sealed manifest SHA-256:
  `975186eaac9e4e6995fa19ded703b643251c9cb3739c4613ba35af1e09e82f95`;
- 12 reportable findings: eight Medium/P2 and four Low/P3;
- four deployment or undefined-policy questions deferred for explicit closure;
- three selected structural destinations: persisted draft audiences, shared
  resource admission, and versioned relational workflow persistence.

Planning does not close a finding. A finding closes only when its original
attack path fails safely, intended behaviour still passes, closure evidence is
recorded and a fresh immutable scan validates the resulting revision.

## Outcomes

We will:

- close all 12 reportable findings and resolve all four deferred questions;
- preserve every intended user journey, API contract and local-first workflow;
- make authorisation, resource admission and workflow consistency owned by
  explicit application boundaries;
- remove lower-layer dependencies on services and reduce broad classes and
  files without changing observable behaviour;
- make PostgreSQL migrations additive, reconciled and safely reversible;
- make project, architecture, API, security and operational documentation agree;
- finish with clean local and GitHub gates plus a sealed deep security scan.

## Non-Breaking Invariants

These rules apply to every work package and are release-blocking:

- Existing authorised actions, published-product access and role journeys keep
  their successful request and response semantics.
- Existing unauthorised actions remain denied and non-enumerating.
- URLs, request fields, successful response shapes and domain states do not
  change without a separately approved, versioned compatibility decision.
- New `409`, `413` and `429` responses occur only for stale transitions,
  exceeded byte limits or exceeded resource budgets.
- CSRF, session, ACG, clearance, archive and signed-token controls stay active.
- Mock providers, local object storage and local development keep working.
- A migration has one authoritative writer. Shadow projections cannot become a
  second independent source of truth.
- Additive schemas remain compatible with rollback code until restore and
  reconciliation drills pass. Destructive downgrade is not a rollback plan.
- Secure tactical controls remain during structural rollout and rollback.
- Each change starts with characterisation or regression tests and passes the
  full relevant gate before the next work package begins.

## Finding Closure Matrix

| Finding                           | Repair                                                                                       | Structural destination                          | Required proof                                                              |
| --------------------------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------- |
| `COEUS-CAN-001` draft search      | Replace the broad draft Boolean with an object-specific audience predicate.                  | Persisted draft-audience projection.            | Unrelated same-ACG search PoC is denied; legitimate audience matrix passes. |
| `COEUS-CAN-002` draft detail      | Apply the same predicate to repository prefilter and selected-object policy.                 | One draft policy API and projection.            | Known unrelated UUID remains non-enumerating; intended detail reads pass.   |
| `COEUS-CAN-006` draft asset       | Recheck audience at grant and redemption, retaining ACG, clearance and token binding.        | Transactionally maintained, revocable audience. | Multi-role PoC is denied and audience removal invalidates prior authority.  |
| `COEUS-CAN-012` upload memory     | Validate first, stream and hash incrementally, stage atomically and reserve in-flight bytes. | Shared upload-byte reservations.                | Peak memory scales with chunk size and concurrency, not payload size.       |
| `COEUS-CAN-026` chat cost         | Reserve principal and deployment provider capacity and cap retained drafts.                  | Shared provider governor.                       | Repeated-ticket PoC is bounded; legitimate chat and refund paths pass.      |
| `COEUS-CAN-027` corpus rewrite    | Add ticket quotas and recovery, then stop whole-corpus mutation.                             | Per-ticket relational aggregate.                | Mutation cost remains stable from 10 to 10,000 tickets.                     |
| `COEUS-CAN-028` pre-auth spool    | Authenticate and validate CSRF before explicit multipart parsing; cap receive bytes.         | Ingress receive gate plus byte reservation.     | Anonymous body causes zero multipart spool writes before rejection.         |
| `COEUS-CAN-030` auth history      | Record only admitted attempts and bound per-source and total retained state.                 | Bounded local correctness with edge defence.    | Ten thousand attempts and many sources remain within configured bounds.     |
| `COEUS-CAN-035` embedding fan-out | Cache or precompute candidates, single-flight misses and bound all work.                     | Shared embedding admission.                     | The 101-call PoC becomes bounded and two-principal fairness passes.         |
| `COEUS-CAN-036` Store embeddings  | Normalise and single-flight query embeddings before reserving capacity.                      | Shared embedding admission.                     | Repeated query embeds once; misses stop at the configured budget.           |
| `COEUS-CAN-037` RFI embeddings    | Preserve the one-run gate, add user/deployment admission and ticket quotas.                  | Shared governor plus lifecycle quotas.          | Repetition across new tickets and processes remains bounded.                |
| `COEUS-CAN-044` QC/cancel race    | Use compare-and-swap for every transition and conditional compensation.                      | Versioned transaction plus outbox.              | Both race orders yield one commit, one conflict and no detached product.    |

## Deferred Security Decisions

The programme also closes scan coverage gaps rather than silently accepting
them:

- `COEUS-CAN-003`: document the trusted proxy chain, forbid direct API reachability
  when proxy trust is enabled, and test `X-Forwarded-For` handling in staging.
- `COEUS-CAN-005`: fail configuration for credentialed wildcard CORS, document
  sibling-origin ownership and exercise CORS plus CSRF behaviour in staging.
- `COEUS-CAN-007` and `COEUS-CAN-008`: define releasability and handling-caveat attributes,
  add denied fixtures and enforce the agreed policy in Store search and detail.

## Ordered Work Packages

### Phase 0: Freeze Behaviour And Decide Security Contracts

Deliver:

- Capture OpenAPI and representative Store, upload, chat, search, auth and
  workflow responses as compatibility fixtures.
- Add semantic OpenAPI comparison against the merge base, not only regeneration
  freshness.
- Add a real PostgreSQL CI service and empty/seeded migration, concurrency and
  rollback harness before any PostgreSQL-dependent change.
- Convert all 12 safe PoCs into repeatable regression tests with positive-path
  counterparts.
- Freeze every codec-backed namespace with golden file and PostgreSQL fixtures.
  First ship a reader for legacy and stable type IDs while writing legacy IDs;
  switch writers only in a later rollback-compatible release.
- Replace the load-sensitive 0.5-second liveness assertion with deterministic
  provider-start and event-loop barriers; run it cleanly 20 times.
- Write ADRs for draft-audience membership, resource units and refund semantics,
  workflow conflict/outbox ownership, and releasability/handling caveats.
- Record baseline p50/p95 latency, upload RSS and temporary storage, provider
  calls, ticket mutation cost and SQL statement counts without coverage tooling.

Gate: the unmodified functional baseline, except the known security PoCs, is
green and reproducible. No implementation starts with a flaky baseline.

### Phase 1: Close Every Immediate Attack Path

Deliver small, independently reviewable patches in this order:

- Central object-aware guards for draft search, detail, grant and redemption.
- Fail fast on unsafe trusted-proxy or credentialed wildcard-CORS configuration;
  retain restrictive defaults and document the supported ingress contract.
- Authentication before multipart parsing, cumulative wire-byte limits,
  streamed staged uploads, deterministic cleanup, and durable per-principal and
  deployment in-flight byte and upload-concurrency reservations.
- Bounded authentication history with an injected clock, empty-key expiry,
  total source-cardinality control and a many-source regression.
- Compare-and-swap for every ticket transition, release and compensation path.
- Per-principal and deployment endpoint quotas for chat, Store, similarity and
  RFI work; single-flight caches and bounded execution for embeddings. Hosted
  enforcement must be atomic across processes, not process-local state.
- Principal and deployment ticket-count limits with operator recovery tooling.

Gate: 12 of 12 PoCs fail safely in the supported boundary, paired legitimate
paths pass and denied work has no expensive or partial side effect. Two-process,
two-connection PostgreSQL tests cover every expensive endpoint and both orders
of competing transitions. Closure remains provisional until the relevant
structural phase and final sealed scan pass.

Rollback: revert only to the preceding secure tactical boundary. Never restore
the broad draft Boolean, pre-auth spool, full buffering, unbounded histories,
unmetered providers or unconditional stale writes.

### Phase 2: Centralise Draft Audience Authorisation

Deliver:

- Introduce a narrow `DraftAudiencePolicy` application port and one domain
  representation for audience reasons.
- Include agreed releasability and handling-caveat attributes in Store policy.
- Add an indexed, additive audience projection keyed by product and principal.
- Backfill idempotently and deny by default when a relationship is ambiguous.
- Shadow-compare live object guards and projected decisions with no disagreement
  before independently cutting over search, detail, grant and redemption.
- Keep tactical guards authoritative until audience updates commit atomically
  with workflow state; otherwise authoritative cutover waits for Phase 4.
- Revoke authority immediately when assignment, role, ACG, clearance or product
  lifecycle changes invalidate the relationship.

Gate: the complete creator, analyst, manager, QC, administrator, unrelated and
multi-role matrix passes for memory and PostgreSQL-supported behaviour. Search
and selected-object decisions cannot drift.

### Phase 3: Own Shared Resource Admission

Deliver:

- Define focused ports for reservations, provider calls and upload staging.
- Implement PostgreSQL-backed atomic leases for principal and deployment
  resources such as provider calls or tokens, embedding calls, concurrent
  search slots, in-flight upload bytes and retained tickets.
- Require reservation context before acquiring an operator-funded provider or
  shared worker. Commit actual use and refund or expire exactly once.
- Deploy in observe-only mode, then enforce deployment ceilings, then principal
  ceilings. Mock/local providers use an explicit safe development policy.
- Provide independently testable, fail-closed switches for observation and each
  enforcement level, with named owners, secure defaults and rollback commands.
- Add saturation, denial, lease-expiry and circuit metrics without actor labels.

Gate: limits pass at `limit - 1`, `limit` and `limit + 1`; two principals both
make progress; crash, timeout and retry accounting has no leaked or duplicated
capacity; denied work performs no expensive side effect.

### Phase 4: Version Workflow Persistence And Side Effects

Deliver through expand, backfill, shadow, cutover and later contraction:

- Define `TicketRepository`, `WorkflowTransactionPort`, `AuditSink`,
  `OutboxWriter` and transactional Store ports before adapters. One transaction
  owner supplies transaction-scoped repository views; only composition selects
  concrete adapters.
- Add per-ticket versioned rows plus transition, product-link and outbox data.
- Keep one authoritative writer and populate the new model as a shadow.
- Make backfills resumable and idempotent; reconcile counts, identifiers,
  versions, relationship reasons and canonical hashes.
- Commit ticket release, product linkage, dissemination, feedback request and
  one uniquely keyed outbox event using version predicates, deterministic lock
  order and a documented isolation level in one short transaction.
- Keep provider calls, notification delivery and object bytes outside the
  database transaction; stage safely and clean abandoned work.
- Cut over one transition class at a time. Retain the legacy model through two
  successive clean candidate validations, each with migration and restore.
- Before rollback, quiesce writers and reverse-project current rows to a verified
  legacy namespace, or retain new reads. A stale snapshot is not a rollback.
- Add fail-closed shadow, read-cutover and tactical rollback switches; refuse
  cutover while reconciliation is incomplete.

Gate: empty and production-equivalent Alembic upgrades, repeated backfill,
shadow comparison, concurrent multi-process transitions, code rollback and
coordinated database/object-storage restore all pass with zero reconciliation
differences, orphan or duplicate records, or data loss. N-1 code runs against
the expanded schema, and every adapter passes one transaction contract suite.
Implementation note, 2026-07-13: hosted PostgreSQL QC release now commits its
versioned ticket, Store projection, audit evidence and notification intent in
one transaction. Durable delivery is retry-fenced and event-ID deduplicated.
Ticket creation and workflow actions now commit ticket and audit together.
Paired links lock deterministically; local batches and pairs are single-process
atomic. Outbox conflicts fail closed. Restore evidence keeps Phase 4 open.

### Phase 5: SOLID And Maintainability Consolidation

Refactor only behind the behaviour and security tests established above:

- Move service-owned contracts into domain or application-port modules so
  domain, persistence and repositories never import from `services`.
- Add an AST gate rejecting domain imports from services, repositories,
  persistence or API; lower-layer imports from services/API; and concrete
  infrastructure construction outside composition or approved builders.
- Complete stable-ID writer cutover and retain legacy readers through the
  rollback window; unknown IDs fail closed.
- Remove remaining manual rollback and broad exception handling in favour of
  the Phase 4 transaction ports and typed failures.
- Split `domain/tickets.py` by lifecycle, intake, assignment, production and
  audit responsibilities while preserving compatibility re-exports, equality
  behaviour and the public aggregate contract.
- Split `services/tickets.py`, `ai_models.py`, `store.py`,
  `acg_applications.py` and `repositories/auth.py` behind compatibility facades,
  preferring 300-line post-refactor headroom below the 350-line gate.
- Separate React mutation orchestration from presentation and consolidate
  `useRequestWorkspaceMutations.ts`, `AiModelPanel.tsx`, and duplicate state
  metadata behind their current public contracts.
- Generate deterministic frontend API types from OpenAPI.
- Add public-interface documentation for application ports, security decisions,
  state transitions, provider accounting and operational failure behaviour.

Gate: no forbidden lower-layer imports, no touched handwritten file over 350
lines, no unapproved OpenAPI difference, equivalent adapter contracts and no UI
journey change. Security-sensitive changed modules maintain 100 percent branch
coverage unless a specifically unreachable branch has a reviewed exclusion;
repository line and branch coverage remain at least 95 percent.

### Phase 6: Documentation, Operations And Release Closure

Deliver:

- Reconcile the root plan, master tracker, feature-spec statuses and development
  story so each has one accurate current state and evidence date.
- Reconcile the specs, ADRs and threat models updated alongside every Phase 1-5
  code change; Phase 6 must not be their first update.
- Correct `ARCHITECTURE.md`, `ARCHITECTURE_DEPLOYMENT.md` and `AI_AGENTS.md`
  so shipped Gemini, OpenAI, Vertex and Bedrock boundaries and current roles are
  described accurately; supersede historical ADR claims rather than rewriting
  their original decisions.
- Add settings-to-`.env.example` parity for supported provider, proxy, timeout,
  throttle and resource controls, with reviewed exclusions.
- Add meaningful OpenAPI descriptions and an API security/usage guide while
  preserving operation IDs and schemas.
- Add focused module and public-interface documentation for ports, domain
  invariants, transitions, accounting and recovery, plus backend and frontend
  developer boundary guides.
- Document API conflict and limit responses, quota tuning, migration,
  reconciliation, rollback, outbox replay, stale-lease recovery and incidents.
- Make CI documentation match workflow files and add Markdown link validation.
- Add consistent status, applicable revision, last-verified and supersession
  metadata to active specs, threat models and runbooks. Historical documents
  remain historical rather than being rewritten as current evidence.
- Regenerate affected user-guide screenshots only after the UI is stable, then
  verify their routes, states and image references in CI.
- Extend the Phase 0 PostgreSQL harness with a real-stack browser journey using
  Customer, JIOC, RFA/CM, Analyst, QC, Administrator and unrelated multi-role
  actors. Cover draft denial, `409`/`413`/`429` recovery, publication, search and
  actual asset-byte download without duplicate mutation or lost input.
- Verify trusted proxy, CORS, ingress limits and handling-caveat policy in an
  authorised staging environment. Do not represent local checks as production.
- Run all local and protected GitHub checks, then seal a fresh deep scan of the
  exact clean release candidate.

Gate: all documentation links and documented commands work; all 12 findings and
four deferred questions have code, test, documentation and closure evidence;
the final scan has no unresolved occurrence from this baseline and no new
reportable finding.

Sprint 17 remains explicitly blocked until an authorised staging boundary exists
for proxy, CORS and ingress checks; local evidence cannot claim their closure.

## Verification And Release Gates

- Backend: Ruff, strict mypy, Bandit, pip-audit, pytest, at least 95 percent line
  coverage and at least 95 percent branch coverage.
- Frontend: Prettier, ESLint, TypeScript, Knip, Vitest and all four 95 percent
  coverage thresholds, production audit and production build.
- Contracts: generated OpenAPI is current and semantic comparison reports no
  unapproved breaking change.
- Browser: retain fast mocked journeys and add a real PostgreSQL/local-storage
  role workflow, accessibility checks and security-denial recovery.
- Migration: upgrade from empty and seeded prior schema, idempotent backfill,
  reconciliation, code rollback, backup restore and eventual retirement review.
- Security: all finding regressions, CodeQL, Semgrep, gitleaks, Trivy, Checkov,
  SBOM, fail-closed ZAP and a final sealed deep scan.
- Stability: concurrency and resource suites pass 20 consecutive executions;
  all full gates pass three clean runs on the release candidate.
- Performance: unaffected authorised operations keep p95 latency within 10
  percent and error rate within 0.5 percentage points of the measured baseline.
- Benchmarks use versioned fixtures and provider stubs, pinned concurrency and
  runner class, documented warm-up, and at least five runs compared by median.
  SQL statements differ by at most two between 10 and 10,000 tickets; upload RSS
  stays within fixed overhead plus active buffers, and spool bytes return to zero.
- CI uses zero release-gate retries, explicit timeouts, retained failure
  artefacts and Playwright traces. Superseded PR checks may cancel, never `main`.

## Documentation Truth Matrix

| Subject                   | Authoritative document              | Required companions                    |
| ------------------------- | ----------------------------------- | -------------------------------------- |
| Delivery state            | Root implementation plan            | Master tracker and development story   |
| Feature behaviour         | Relevant `docs/specs/` file         | OpenAPI, user guidance and tests       |
| Expensive decisions       | New or updated ADR                  | Architecture guides and code contracts |
| Threats and residual risk | Relevant `docs/threat-model/` file  | Finding traceability and runbooks      |
| Operation and recovery    | `docs/runbooks/`                    | Configuration examples and CI checks   |
| Scan closure              | This plan plus sealed scan identity | Master tracker and development story   |

Documents must distinguish current local support, future migration references,
staging verification and production evidence. Historical evidence remains
historical and cannot be presented as the current release state.

## Definition Of Done

Sprint 17 is complete only when:

- every row in the finding matrix and every deferred decision has accepted
  implementation and verification evidence;
- intended user and administrator functionality remains available through the
  compatibility, unit, integration and real-stack browser gates;
- the selected structural boundaries are active, observable and rollback-safe;
- no unresolved documentation contradiction or broken relative link remains;
- all local and required GitHub checks pass on the exact clean revision;
- a fresh sealed deep security scan reports no unresolved baseline occurrence
  and no new reportable finding;
- `main`, GitHub and the release evidence identify the same immutable commit.
