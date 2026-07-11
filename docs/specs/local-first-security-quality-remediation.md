# Local-First Security And Quality Remediation Spec

## Goal

Close every validated finding from the 2026-07-10 repository assessment and
raise the codebase's SOLID, readability, maintainability and verification
quality without turning GCP into a current runtime dependency.

The sealed scan of revision `72a0dc58` reported a second baseline of 16
reportable findings, three medium and thirteen low. Sprint 14B keeps this spec
open until those occurrences are closed on a clean immutable revision.

## Sealed Sprint 14B Finding Baseline

### Immediate boundaries

1. Restrict PostgreSQL to loopback and remove the known superuser credential.
2. Move Store and RFI provider I/O away from the event loop.
3. Cap per-ticket chat count and aggregate bytes.

### Shared resource budgets

1. Stream asset downloads and cap aggregate in-flight bytes.
2. Bound Store and RFI candidate, comparison and provider-call work.
3. Coalesce or semaphore readiness database checks.
4. Cap product asset metadata, ticket attachments and analyst draft history.
5. Paginate ticket and routing collections with bounded summary responses.

### Monitoring and CI integrity

1. Preserve audit cursors in the client and expose older-event navigation.
2. Remove ZAP warning suppression and define reviewed FAIL, WARN and IGNORE
   rules with a deliberately vulnerable CI fixture.

## Product Boundary

- Coeus is currently a local, single-instance application.
- PostgreSQL, local files, local object storage and optional local integrations
  remain the supported runtime.
- GCP Terraform and validation material are retained only as an inactive future
  migration reference.
- No current GitHub workflow may authenticate to GCP, push an image, change
  infrastructure or deploy traffic.
- The future GCP path must remain single-writer until transactional shared-state
  adapters and distributed security controls are implemented and verified.

## Validated Issue Inventory

### Current-policy response authorisation

One actor-scoped task projection must re-check current Store access before
returning linked-product metadata from all seven affected paths:

1. Assignment response.
2. Task list.
3. Task detail.
4. Note update response.
5. Work-package update response.
6. Draft save response.
7. QC submission response.

### Bounded request work

1. Customer similarity notices must not score an unbounded corpus.
2. Customer join must authorise the requested target before bounded pairwise
   comparison.
3. Manager similarity lists must use a bounded candidate set.
4. Manager link mutation must not rescan the corpus to build its response.
5. Store pagination must occur in the relational query before child hydration.

### Local security-state invariants

1. Unauthenticated traffic must not erase privileged audit evidence.
2. Login-attempt capacity handling must preserve every active enforcement
   history, including pre-lockout failures.
3. The pending-registration ceiling must be atomic for concurrent local
   requests.
4. QC asset size and SHA-256 metadata must be derived from the served bytes.
5. Current runtime and future migration reference must enforce one writer until
   shared transactional session state exists.

### Engineering quality gaps

1. Backend line and branch coverage must be measured and enforced separately at
   95 percent or higher.
2. At least one Playwright workflow must use the real browser, Vite frontend and
   FastAPI backend without intercepting API requests.
3. The application composition root must be split into named, typed assembly
   units instead of manually wiring every service in one function.
4. Storage and high-coupling repository boundaries must depend on narrow
   protocols where the project has a real substitution boundary.
5. `AnalystTaskDetail` must separate orchestration from focused rendering and
   mutation units.
6. Frontend API calls must use one consistent request boundary.
7. Runtime security validation must be decomposed into readable rule groups.

### Completion-audit gaps

The final independent review added seven closure requirements beyond the
original 17 findings:

1. Similarity embedding work must not block the FastAPI event loop.
2. Login rollback must not erase a concurrent per-username failure or lock.
3. Concurrent registration decisions must create at most one account and one
   terminal decision.
4. Partial object writes must never leave served bytes or orphaned final paths.
5. Analyst task and linked-product projections must have explicit work limits.
6. Lockout threshold and duration configuration must both be positive.
7. The dormant GCP reference must fail closed before any plan, apply or deploy.

## Delivery Order

### Phase 1: Evidence and regression baselines

- Re-open every current source-to-sink path from the sealed finding index.
- Add a failing regression test or realistic reproduction for each broken
  invariant before its implementation change where practical.
- Record the legitimate control that each fix must preserve.

### Phase 2: Central security boundaries

- Add the actor-scoped task projection and move all seven callers to it.
- Bound and pre-filter similarity candidates, add pairwise comparison, and move
  Store pagination into the SQL projection.
- Add append-only local audit evidence, atomic local registration capacity,
  enforcement-preserving login-attempt retention, and byte-derived QC metadata.

### Phase 3: Runtime boundary and maintainability

- Remove active cloud deployment capability and document its readiness gates.
- Enforce a single current writer in runtime and reference configuration.
- Split the composition root and introduce protocols only at real provider or
  persistence boundaries.
- Decompose the analyst task UI and consolidate API request style.

### Phase 4: Verification quality

- Enforce independent backend line and branch thresholds.
- Add meaningful tests until both backend measures reach at least 95 percent.
- Add a real browser-to-API Playwright workflow and run it locally and in CI.

### Phase 5: Closure

- Run all repository quality, build, dependency, security and line-limit gates.
- Re-run every original exploit reproduction against the fixed checkout.
- Run and seal a fresh whole-repository Codex Security scan.
- Update the threat model, ADRs, development story and this plan with exact
  evidence and remaining deferred risks.

## Subagent Work Contracts

Every subagent receives a bounded issue family and must:

1. Treat the current checkout and sealed finding evidence as authoritative.
2. Respect local-first, single-instance scope and avoid adding cloud services.
3. State the attacker-controlled input, preconditions, violated invariant and
   legitimate behaviour to preserve.
4. Identify the narrowest shared enforcement boundary and every equivalent
   caller or sink.
5. Name exact source and test files, proposed assertions and bypass cases.
6. Keep analysis read-only unless explicitly assigned a non-overlapping edit
   set by the orchestrator.
7. Return a definition-of-done checklist and unresolved product decisions.

The orchestrator owns final edits, integration, broad checks, documentation and
the completion audit. A subagent summary is evidence for planning, not proof
that a finding is fixed.

Sprint 14B uses these non-overlapping editing contracts:

- Database and network worker: Compose, database roles, migrations and local
  database runbooks only.
- Async and compute worker: Store/RFI embeddings, ranking budgets and liveness
  tests only.
- Aggregate-boundary worker: chat, attachment, asset, draft and list limits,
  plus their schemas and focused tests.
- Storage and health worker: streaming downloads, download concurrency and
  readiness coalescing/timeout only.
- Monitoring and CI worker: audit pagination, ZAP policy, controlled fixture
  and required-check documentation only.
- Documentation and Plan Keeper: the root plan, master tracker, ADRs, threat
  models, development story and runbooks only.
- Audit atomicity worker: chat, intake, submission, attachment and information
  save-plus-audit boundaries and exact rollback regressions only.
- Aggregate concurrency worker: repository compare-and-swap, conditional RFI
  rollback and coordinated lost-update regressions only.

Each worker must return changed files, the invariant restored, the exact tests
run, remaining proof gaps and a maximum/maximum-plus-one or equivalent bounded
regression. One editing owner is responsible for each shared file.

## Definition Of Done

### Security findings

- The original assessment contained 17 items: 16 sealed code findings plus one
  topology-contained multi-replica item. All 16 sealed baseline findings no
  longer reproduce. The multi-replica stale-session primitive remains outside
  the supported topology and is blocked by single-writer runtime, IaC and
  migration-readiness gates until a transactional session adapter replaces it.
- All legitimate control cases still pass through the same real boundaries.
- Alternate caller and equivalent-sink review finds no unpatched variant.
- Threat-model controls describe the implemented local behaviour accurately.

### Local runtime and future GCP path

- Default setup, scripts and documentation run locally without GCP credentials.
- Current execution and the inactive GCP reference permit only one API writer.
- The GitHub reference only validates and builds locally, and Terraform plan or
  apply is blocked until its readiness checklist is satisfied.
- No real GCP project, deployment or secret is required or contacted.

### Code quality and SOLID

- Route handlers and React rendering units remain focused.
- Side effects and provider boundaries are explicit and testable.
- Concrete dependencies remain only where substitution would add no real value.
- No changed hand-written file exceeds 350 lines.
- Ruff complexity reports no C901 violation at the configured threshold.

### Tests and delivery gates

- Backend line coverage is at least 95 percent.
- Backend branch coverage is at least 95 percent.
- Frontend line and branch coverage are each at least 95 percent.
- A real Playwright workflow completes without API interception.
- Ruff, mypy, ESLint, TypeScript, Prettier, Knip, builds, dependency audits,
  Bandit, Semgrep, CodeQL-compatible analysis and file-line checks pass.
- A fresh sealed security scan has no unresolved occurrence from the original 17
  findings. Any newly discovered finding is fixed or explicitly retained with
  evidence that completion is not being claimed.

### Verification-scan addendum

- Scan `a089e83c-afc7-4213-8763-4a5e5759598d` of `7165e49e` confirmed the
  original 16 closures and reported three new Low/P3 findings: chat audit
  atomicity, intake audit atomicity and RFI stale-snapshot overwrite.
- Definition of done: injected audit failure restores the exact prior ticket or
  removes a new ticket; successful audited mutations emit exactly one event;
  stale RFI work returns `409 ticket_changed` without erasing newer state.
- Suppressed but real debt is also closed: submission, attachment and
  information mutations use the audited boundary; request summaries paginate
  without detail fan-out; dictation discloses browser-dependent remote audio
  processing; container references are version and digest pinned.
- Release closure requires a later immutable whole-repository scan with zero
  reportable findings.

### Sprint 14B sealed baseline

- Every one of the 16 sealed-scan PoCs fails safely on the fixed revision.
- Legitimate use through each original entrypoint still succeeds.
- Equivalent callers and sibling sinks have been reviewed and recorded.
- No rejected over-budget operation changes persistence, timeline, audit or
  object-storage state.
- PostgreSQL is loopback-only and the application role is not a superuser.
- A delayed provider does not block independent event-loop work.
- List and mutation response sizes are bounded by documented budgets.
- The ZAP fixture fails its required check and still publishes evidence.
- A fresh sealed repository-wide scan of a clean revision has no unresolved
  occurrence from the 16-finding baseline and no newly reportable finding.

## Pre-Seal Verification Evidence

- Backend: 490 tests, 98.28 percent line coverage and 95.05 percent branch
  coverage.
- Frontend: 322 tests, 98.77 percent line coverage and 95.54 percent branch
  coverage.
- Browser: three Chromium flows, including a real Vite-to-FastAPI path without
  API interception.
- Static and supply chain: Ruff, mypy, Bandit, pip-audit, pnpm audit, Semgrep,
  Gitleaks, Actionlint, Checkov and Trivy passed.
- Delivery: Prettier, ESLint, TypeScript, Knip, production build, Docker build,
  Terraform format, validate and four tests, and the 350-line gate passed.
- Closure remains conditional on the final immutable-revision Codex Security
  scan.

## Non-Goals

- Deploying or testing a live GCP environment.
- Adding GCS, Pub/Sub, Cloud Run or cloud-hosted AI as current dependencies.
- Multi-region or multi-writer operation.
- Replacing useful local-first code with speculative enterprise abstractions.
