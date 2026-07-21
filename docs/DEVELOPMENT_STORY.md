# Coeus Development Story

Sprint 1 to Sprint 13 entries live in
[DEVELOPMENT_STORY_SPRINTS_01-13.md](DEVELOPMENT_STORY_SPRINTS_01-13.md). The
2026-07-06 continuation lives in
[DEVELOPMENT_STORY_2026-07-06.md](DEVELOPMENT_STORY_2026-07-06.md), and the
2026-07-13 security milestone lives in
[DEVELOPMENT_STORY_2026-07-13.md](DEVELOPMENT_STORY_2026-07-13.md). The latest
admin command-centre milestone is recorded in
[DEVELOPMENT_STORY_2026-07-17.md](DEVELOPMENT_STORY_2026-07-17.md), and the
customer-search and JIOC-agent milestone is recorded in
[DEVELOPMENT_STORY_2026-07-18.md](DEVELOPMENT_STORY_2026-07-18.md). The current
agent-safety and LiteLLM work is in
[DEVELOPMENT_STORY_2026-07-20.md](DEVELOPMENT_STORY_2026-07-20.md), and the
production-safe Store startup repair is in
[DEVELOPMENT_STORY_2026-07-21.md](DEVELOPMENT_STORY_2026-07-21.md).

## 2026-07-11 cross-role usability and documentation accuracy

- Completed the desktop cross-role audit across customer, JIOC, team manager,
  analyst, QC, Store, team and administrator workspaces.
- Added manager work review, deliberate QC controls, safer record switching,
  structured multi-analyst assignment, clearer task context, profiles, calendar
  corrections, readable workflow language and accessible command navigation.
- Fixed JIOC similar-request access by aligning its workflow permission boundary
  with the routing queue and updated the real end-to-end workflow fixture.
- Added Gemini, OpenAI, Vertex AI and Bedrock runtime provider administration with
  connection tests and explicitly warned app-wide activation.
- Re-audited active documentation and screenshots. Kept local development as the
  supported runtime, documented local multi-user evaluation, and made GCP and
  Kubernetes explicit migration targets with readiness gates rather than active
  deployment claims.
- PRs #98 to #100 passed backend, frontend, CodeQL, DAST, container, Semgrep,
  Checkov, Gitleaks, SBOM and Terraform checks before merge.

## 2026-07-11 JIOC workflow restructure, QC release, teams and calendars

- Renamed the workflow roles to plain names (Customer, RFA/CM Manager and Team
  Member, Analyst) and added the JIOC Team Member role; legacy persisted role
  strings decode through `RoleName._missing_` aliases.
- Replaced the manager route-review stage with a single JIOC queue: capability
  agents advise, a JIOC member decides collection (CM) or assessment (RFA),
  with recorded override reasons. Retired `ROUTE_ASSESSMENT` and the manager
  review states via `TicketState` aliases.
- Added the customer collect choice: a CM-routed ticket pauses in
  `COLLECT_CHOICE` until the requester picks raw collect only or collect plus
  RFA analysis (owner-only, CSRF-validated, audited).
- Added the manager approval chain (`MANAGER_APPROVAL`) with separation of
  duties and multi-analyst assignment (one to five analysts; reassignment
  deactivates prior assignments instead of overwriting them), splitting out
  `services/analyst_assignment_service.py` and `services/manager_approval.py`.
- Moved the final release from managers to Quality Control: QC approval now
  publishes, disseminates, raises the feedback request and notifies the
  requester in one compensated step (`services/qc_release.py`); an analysed
  collect is instead forwarded to RFA assignment with the collect linked and
  still DRAFT. Retired `MANAGER_RELEASE` (aliases to `QC_REVIEW`), the release
  endpoints and the ReleaseQueuePanel; the release hardening tests moved to
  `test_qc_release_api.py`.
- Fixed a live-only privilege bug found in the walk-through: restored user
  records kept the permission snapshot from seed time, so revoked release
  permissions survived upgrades. `SeedUserRepository` now re-derives
  permissions from persisted roles on startup, with regression coverage.
- Added organisational teams, member profiles and team calendars with a
  deterministic availability service (calendar plus live assignments), the
  My Team page and availability counts in the assignment panel.
- Docs: ADR 0022, specs and threat models for the JIOC restructure and for
  teams/profiles/calendars; superseded the manager-final-release documents;
  refreshed the workflow architecture, roles, user guide and setup docs.
- Both suites green at the 95% gates; every phase also verified live in the
  browser, including the CM-to-RFA analysed-collect journey.

## 2026-07-09 Access-control audit rollback

- Made audited ACG administration, ticket collaboration, related-request links
  and requester lifecycle actions failure-atomic, preventing access or state
  changes from surviving a failed audit write.
- Extended rollback coverage across RFA/CM routing, RFI decisions, analyst work,
  QC decisions and release, including suppression or removal of downstream Store,
  asset and notification side effects.
- Made notification and email persistence, administrator AI-model changes and
  authentication session lifecycle operations restore their exact prior state
  when persistence or audit recording fails.
- Hardened Store ingestion so failed storage or audit work cannot leave orphaned
  bytes, metadata or a false product-created event. Regression tests and relevant
  threat models cover the failure boundaries.
- Removed retired workspace sanitisation so old Project permissions and records
  fail closed instead of being accepted by the runtime persistence codec.

## 2026-07-08 No-match consent

- Added Part C no-match consent. Zero-offer RFI searches now enter
  `RFI_NO_MATCH` and record `rfi_no_match` on the ticket timeline instead of
  tasking new work automatically.
- Added an owner-only, CSRF-protected consent endpoint and customer workspace
  prompt. Yes moves the ticket to `ROUTE_ASSESSMENT`; No moves it to
  `CANCELLED` with the fixed reason `customer declined tasking after no-match`.
- Updated journey mapping, dashboard search metrics, similar-request state scope,
  audit coverage and documentation for the new state.

## 2026-07-08 Similar request detection

- Added Part B similar-request detection for open tickets from `RFI_SEARCHING`
  through `MANAGER_RELEASE`, using deterministic lexical and embedding signals
  with RRF scoring and region/output-format boosts.
- Added customer-facing similar-request notices that reuse existing ticket
  visibility before showing references or titles. Hidden matches produce only a
  neutral assessing-team notice. Customers can join visible matches as viewers
  or continue their own request.
- Added manager routing-queue panels that show similar open requests before route
  decisions. Managers can link tickets as related, with reciprocal ticket IDs,
  timeline entries on both tickets and `tickets_linked` audit events.
- Added backend API/scoring tests and frontend Vitest coverage for customer and
  manager panels, including failed join/link actions.

## 2026-07-07 Full-application audit and remediation

- Ran a three-track audit (frontend, backend, AI agents) that found broken
  functionality, silent failure modes and security gaps; recorded decisions in
  ADR 0015 and `docs/threat-model/audit-remediation.md`.
- Made `COEUS_LLM_PROVIDER` authoritative: an API key never switches the
  provider implicitly, flagged messages are refused on every provider path and
  are no longer extracted, and Gemini failures degrade to the mock reply
  instead of losing the customer's message. Removed the unimplemented gemma
  providers and the empty `agents/` package directory.
- Hardened the prompt-injection scanner (normalisation plus regex marker
  families) and stopped the intake extractor inventing operational questions
  and success criteria, so the completeness checklist reflects only what the
  customer said.
- Fixed the capability agents' tokenisation (punctuation, plurals, the
  "unknown" false positive) and made CM feasibility require a genuine
  collection signal; RFI search now ranks every permitted published product
  instead of the first browse page and 2-character regions such as UK score.
- Closed lifecycle dead ends: added `CLOSED_DELIVERED` with an owner-only
  confirm-delivery endpoint and button, analyst reassignment during
  production, idempotent work-package updates and same-queue route override
  with the override-reason UI.
- QC approval now validates up front, sanitises time periods to ISO dates,
  writes downloadable placeholder bytes at ingestion and rolls back the store
  product if the ticket update fails.
- Security: session IDs hashed at rest, self-service password change with
  forced rotation after admin resets, proxy-aware login throttling with
  lockout decay, need-to-know directory search, asset tokens moved to the
  `X-Asset-Token` header with no-store caching, CSRF on access diagnostics,
  and `TICKET_READ_ALL` no longer confers write access.
- Frontend: a shared mutation-error helper ended the silent-failure pattern
  across routing, analyst, QC, feedback, notifications and upload; global 401
  handling routes to the session-expired page; partial intake saves omit blank
  fields; the QC checklist resets between products; unreachable pages gained
  navigation and deep-link handling; dead components were removed.
- Verified the whole lifecycle in the running app: chat intake with injection
  refusal, RFI search and offer rejection, capability review, same-queue
  approval, analyst production, QC approval, release with notification,
  delivery confirmation and a header-token asset download. The live run
  surfaced and fixed three integration gaps: `X-Asset-Token` missing from the
  CORS allow list, cacheable grant/download responses replaying stale tokens,
  and the routing plan update record missing from the persistence codec
  allowlist.
- Checks: pytest (269 tests, 95.9% coverage), Vitest (280 tests, 99% lines),
  mypy, Ruff, tsc, ESLint, Prettier and the 350-line limit all pass.

## 2026-07-08 Architecture documentation

- Added a grounded architecture guide split by responsibility across three
  cross-linked documents with ten validated Mermaid diagrams:
  `docs/ARCHITECTURE.md` (system context, layered application, data and
  persistence, security and need-to-know), `docs/ARCHITECTURE_WORKFLOW.md` (the
  request journey state machine, the end-to-end sequence, the AI agents and
  hybrid RFI search internals) and `docs/ARCHITECTURE_DEPLOYMENT.md` (local
  runtime topology, the future Google Cloud Platform reference design, the
  local-vs-GCP provider matrix and scaling notes).
- Linked the guides from the root README and the documentation index, and
  documented the embedding provider settings, the optional `embeddings` extra
  and the backfill command in `docs/SETUP.md`.

## 2026-07-09 Legacy workspace removal

- Removed the legacy workspace feature from backend routes, services, seed
  data, frontend navigation, admin shortcuts, client methods and Store
  workspace metadata/filtering.
- Removed the remaining ticket-level suggested workspace field and renamed
  routing plan records to workflow plan updates.
- Removed active runtime shims for retired workspace state. The persistence
  decoder rejects older retired workspace payloads during local startup.
- Added ADR 0018 and refreshed the ACG/product access threat model and Sprint 3
  spec to record the retirement decision.

## 2026-07-10 Local-first security and quality remediation

- Replayed the sealed 17-finding assessment and fixed the shared enforcement
  boundaries rather than patching individual response routes.
- Added current-policy linked-product projection to every analyst task response,
  query-level Store paging, similarity budgets, pairwise link scoring and
  worker-thread execution for synchronous embeddings.
- Replaced bounded audit evidence with append-only memory, file and PostgreSQL
  stores; protected login rollback with per-username mutation tokens; made
  registration capacity and decisions atomic; and made object writes atomic.
- Kept Coeus local and single-instance. The GCP reference now has no cloud
  authentication or deployment step, and Terraform fails closed until the
  future migration gates are deliberately completed.
- Improved SOLID boundaries through typed composition, narrow repository and
  storage protocols, a functional frontend API transport, and focused analyst
  task hooks and rendering panels.
- Strengthened CI with independent backend line and branch gates, Prettier,
  Knip, real local-stack Playwright and Terraform readiness tests.
- Checks before the final security seal: 490 backend tests at 98.28 percent line
  and 95.05 percent branch coverage; 322 frontend tests at 98.77 percent line
  and 95.54 percent branch coverage; 3 Playwright flows; Ruff, mypy, Bandit,
  pip-audit, pnpm audit, Semgrep, Gitleaks, Actionlint, Checkov, Terraform,
  container build, Trivy, production build and file-line gates all passed.

## 2026-07-10 Sprint 14B post-seal remediation opened

- Sealed a standard whole-repository review of revision `72a0dc58`. It reported
  16 findings: three medium and thirteen low.
- Reopened Sprint 14 rather than claiming completion. The new baseline covers
  local PostgreSQL exposure, async/provider and matcher availability, aggregate
  metadata/history growth, unpaginated responses, readiness fan-out, audit UI
  pagination and ZAP fail-open behaviour.
- Kept local-first and single-writer scope authoritative. The GCP reference
  remains inactive and every cloud-creating target must retain the migration
  gate.
- Defined Sprint 14B completion as fixed-boundary regression evidence, all
  quality/security gates and a fresh sealed scan of a clean immutable revision.
- The concurrent intake, prioritisation and capability-recommendation work is
  unsealed. It must be integrated and scanned explicitly or excluded from the
  remediation release candidate.

## 2026-07-10 Sprint 14B verification remediation

- Integrated the complete feature and remediation slice as `7165e49e`; full
  backend, frontend, browser, container and security gates passed before scan.
- Sealed verification scan `a089e83c-afc7-4213-8763-4a5e5759598d`: all 16
  baseline findings were closed, while three new Low/P3 integrity findings were
  reported.
- Added failure-atomic audited ticket saves, exact rollback for new and existing
  tickets, repository compare-and-swap, conditional RFI rollback and coordinated
  concurrency regressions.
- Closed non-reportable quality debt with compact cursor-paged request summaries,
  selected-only details, browser dictation disclosure and digest-pinned runtime
  images. Full post-fix gates and the final immutable scan remain pending.

## 2026-07-12 AI model administration hardening

- Integrated the distinct provider and model administration work without
  replacing the newer user-management filtering and confirmation behaviour.
- Added bounded live model discovery for OpenAI and Gemini, persistent custom
  model identifiers, explicit activation, safe provider error mapping and
  append-only catalogue refreshes that do not remove existing choices.
- Improved keyboard, focus, loading and error behaviour in the admin UI, and
  documented the local persistence, provider capability and migration model.
- Verified the updated admin experience in the running local application. The
  release gates passed with 644 backend tests at 97.64 percent total coverage
  and the complete frontend suite at 98.78 percent line and 95.12 percent
  branch coverage.

## 2026-07-12 Workflow integrity, oversight and delegated ACG access

- Added a universal Access Groups workspace where every active user can browse
  the bounded catalogue, apply with a justification, track status and withdraw
  a pending application.
- Added one-to-eight delegated administrators per active ACG. Platform
  administrators manage the roster, while delegated administrators can approve
  or reject only their own groups and cannot decide their own applications.
- Made analyst assignment team-authoritative across each manager's RFA or CM
  area, added JIOC-wide read-only ownership and capacity oversight, and repaired
  rework, clarification, loading, feedback and calendar workflow integrity.
- Hardened local startup, including a Windows-safe IPv4 database default,
  coordinated reset, PostgreSQL exposure, migrations and the documented GCP
  and Kubernetes migration gates. Missing user-uploaded bytes are never
  replaced by synthetic placeholders on restart.
- Verification passed with 674 backend tests at 98.21 percent line and 95.10
  percent branch coverage, and 400 frontend tests at 98.60 percent line and
  95.07 percent branch coverage, plus
  formatting, lint, type, dead-code, contract, build, dependency-audit,
  security-policy and line-limit gates.

## 2026-07-12 Calendar and intelligence-store UX integration

- Integrated Claude's month-grid team calendar onto the current workflow and
  ACG baseline without replacing the newer team, profile or availability
  safeguards.
- Added inclusive multi-day blocks for leave, courses, duty travel,
  appointments and other commitments, with bounded validation, audited writes
  and derived availability counts.
- Made the Intelligence Store search-first for ordinary users while preserving
  authorised browse-all access for store managers and administrators and
  owner-team scoped product views.
- Verification passed with 682 backend tests at 98.22 percent line and 95.05
  percent branch coverage, 411 frontend tests at 98.61 percent line and 95.10
  percent branch coverage, and all three Playwright end-to-end journeys.

## 2026-07-17 Grounded retrieval and duplicate assurance

- Added an independent Search and embeddings administration boundary with its
  own encrypted Gemini credential, persisted provider and model selection,
  explicit egress confirmation, connection test and generation-aware re-index.
  The quality-first production choice is `gemini-embedding-2` at 1,536
  dimensions, while local and CI runtimes remain offline on `token-hash-v2`.
- Added bounded local PDF and DOCX extraction, page-aware chunks, PostgreSQL
  full-text plus pgvector retrieval, access-prefiltered evidence, stable
  citations and persisted RFI search snapshots. Active RFI, RFA and collection
  tickets share the generation index for full-corpus duplicate discovery.
- Added customer join notices and manager duplicate controls with route, team,
  time-window and operation context. Hidden-ticket responses preserve the
  zero-signal rule, and link, duplicate and withdrawal actions are transactional
  and audited.
- Live browser testing found and fixed two production-only ranking defects. A
  newly submitted request no longer disables compatible product vectors merely
  because the corpus changed, and partial or weak semantic coverage can no
  longer suppress a strong lexical ticket match. The running app returned a
  92 percent similar open RFI and a hybrid cited Intelligence Store offer;
  manager retrieval also returned active RFA work with route and team context.
- Reconciled runtime-created PostgreSQL tables with Alembic revisions `0007` to
  `0011`, added an old persisted codec identity alias and proved the drifted
  local database upgrades to `20260717_0013` without deleting credentials or
  application data. Docker API health, pgvector and the migrated schema were
  verified against the live local stack.
- Final backend verification passed with 1,129 tests and one intentional skip
  at 98.16 percent line and 95.12 percent branch coverage. Ruff, mypy,
  architecture, line-limit, documentation, security-policy, OpenAPI, Compose,
  dependency-audit and production-build gates passed.
- The complete frontend suite passed at 98.66 percent line and 95.03 percent
  branch coverage. ESLint, TypeScript, Prettier, Knip and the production build
  also passed.
