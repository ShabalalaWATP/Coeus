# Coeus Development Story

## 4 August 2026: canonical team calendars and manager commitments

Migration `20260804_0041` completed the remaining canonical calendar vertical.
Team-scoped events now use the same previewed/versioned command boundary as
personal activity and require exact, transactionally revalidated
`calendar:manage` authority. Manager-created commitments have a separate
subject acknowledgement/dispute lifecycle, reset-and-notify behaviour and
authorised-successor maintenance. Cross-source occurrences now deduplicate by
exact identity while preserving provenance and restoring a lower-priority
source when the winner disappears. Conflicting legacy overlaps fail unknown.
The interface adds keyboard-accessible month, week and agenda modes, commitment
responses and authorised team-event creation. Unit, API, component and real
PostgreSQL coverage accompanies the change.

Historical development milestones are archived by period:

- [Sprints 1 to 13](DEVELOPMENT_STORY_SPRINTS_01-13.md)
- [6 July continuation](DEVELOPMENT_STORY_2026-07-06.md)
- [7 July full-application audit](DEVELOPMENT_STORY_2026-07-07.md)
- [13 July security milestone](DEVELOPMENT_STORY_2026-07-13.md)
- [17 July admin command centre](DEVELOPMENT_STORY_2026-07-17.md)
- [18 July customer search and JIOC agents](DEVELOPMENT_STORY_2026-07-18.md)
- [20 July agent safety and LiteLLM](DEVELOPMENT_STORY_2026-07-20.md)
- [21 July production-safe Store startup](DEVELOPMENT_STORY_2026-07-21.md)
- [22 July security boundaries and product-first results](DEVELOPMENT_STORY_2026-07-22.md)
- [Early July workflow and architecture milestones](DEVELOPMENT_STORY_2026-07-EARLY.md)

The retained entries below are grouped by delivery milestone rather than strict
date order. They are historical evidence, not current operating instructions.

## 2026-08-04 Sprint 24 bounded implementation gate

- Replaced hard-coded fixture assignees with deterministic team-local
  allocation from effective, active, assignment-eligible postings, working
  patterns and projected load. Added explicit idle, loaded, overloaded and
  unavailable examples with two bounded PostgreSQL reservations.
- Differentiated all 24 fictional analyst profiles, introduced two synthetic
  clearance levels and at least seven least-privilege ACG combinations, and
  made analyst 24 an actually inactive account as well as a suspended posting.
- Added a non-overlapping historical transfer, a live machine-readable fixture
  integrity report, and a reauthenticated exact-identifier reconcile command
  that preserves local additions and refuses unsafe drift categories.
- Completed same-leaf accountable package handover with authoritative current
  ticket assignment, versioned grant/package/participant/reservation evidence,
  target capacity checks, actor-scoped replay and atomic history, audit and
  outbox records. Independent code and security review found no residual issue
  after lock-order, ownership, replay and migration-downgrade repairs.
- Added a bounded read-only organisation/capacity drift report and a narrow
  serialisable repair command for safe terminal or elapsed reservations. The
  runbook keeps destructive, ambiguous and authority-changing repairs outside
  this tool.
- Excluded suspended or otherwise inactive Analyst accounts at planning,
  reservation, replay and direct persistence boundaries. Real PostgreSQL tests
  prove replay fails closed after account suspension.
- Added demand-range evidence across all seven delivery leaves and 48 paired
  deterministic routing cases. The relational release remains distinct and
  unapproved, so it cannot inherit the established routing release approval.
- Completed whole-series daily and weekly calendar creation, editing and
  cancellation with one bounded, DST-safe expansion across personal, team,
  aggregate, forecast and reservation reads. Occurrence exceptions and
  edit-this/edit-future remain later enhancements.
- The authoritative backend gate passes 2,410 tests with one intentional
  compatibility skip at 98.16 per cent line and 95.04 per cent branch coverage.
  The full frontend gate passes at 98.77 per cent line and 95.04 per cent branch
  coverage. Ruff, strict mypy, line limit, architecture, dead-code, docs,
  Mermaid, security policy, OpenAPI, TypeScript, ESLint and Prettier checks pass.
- Ten established secure-workflow and eight Sprint 24 real-PostgreSQL browser
  journeys pass. Active organisation authority and the relational routing
  context remain disabled pending independent approval, protected CI and an
  explicit cutover decision.

## 2026-08-03 Bounded recurring capacity

- Expanded validated daily and weekly calendar recurrence for conserved
  capacity while preserving local wall time across daylight-saving changes.
- Kept malformed, overlong and exception-bearing recurrence fail-closed and
  bounded the candidate query to 500 rows.
- Added focused recurrence, DST and corruption regressions. The focused 20
  backend tests and the real PostgreSQL fixture/reservation journey pass. The
  complete frontend gate passes at 98.75 per cent lines, 95.11 per cent
  functions and 95.00 per cent branches.

## 2026-08-03 Atomic package planning

- Added a manager-facing, previewed plan-and-reserve operation to canonical
  team-board packages. It refines effort, remaining work, due date and priority
  while reserving the accountable analyst's conserved capacity.
- Rechecks exact `task:assign` lineage, active workflow-leg ownership and the
  analyst's one eligible posting for the full interval. Command and reservation
  identities are actor and payload bound.
- Commits package version, reservation, immutable history, command journal,
  audit and outbox together under serialisable execution. Real PostgreSQL apply
  and exact replay pass, and the UI requires a separate review and confirm step.

## 2026-08-03 Hierarchical workforce planning audit

- Audited the current flat team model, route queues, analyst workbench,
  calendars, assignment eligibility, JIOC capacity context, canonical seed and
  running local data before proposing an organisational expansion.
- Confirmed that current team work is queue/list based rather than Kanban,
  headcount is used only as a binary routing signal, managers still assign
  people manually, and the four canonical analyst personas cannot demonstrate
  realistic RFA and CM capacity or specialisation.
- Planned an explicit organisation hierarchy, action-specific descendant
  management grants, canonical personal/team calendars, workflow-derived team
  boards, enhanced work packages and transactional capacity reservations.
- Defined a balanced 53-person fictional cohort containing 24 production
  analysts: 14 assigned solely to RFA and ten assigned solely to CM. Every
  person has one effective home unit, with non-overlapping transfers and no
  simultaneous personnel postings. Added seed integrity,
  drift-reconciliation and bounded workload requirements.
- Recorded the proposed architecture in ADR 0049 and added a dedicated threat
  model and phase-by-phase acceptance matrix. This entry records planning only;
  no Sprint 24 runtime behaviour is claimed.
- Accepted ADR 0049 and the Phase 0 decision pack for phased implementation.
  The approved workforce has one effective home unit per person, 14 RFA and ten
  CM analysts, and no simultaneous personnel postings. Phase 1 baseline
  correctness work then began; later hierarchy behaviour remains unclaimed.

## 2026-08-03 Hierarchical workforce Phases 1 and 2

- Corrected legacy team availability so total roster, active people,
  assignment-eligible analysts and free analysts are distinct. Inactive,
  non-analyst, manager and overlapping-home records cannot manufacture
  delivery capacity.
- Restricted named candidate enumeration to directly managed teams and ten
  results, rechecked current team and analyst availability at assignment, and
  added process-local race guards while PostgreSQL reservations remain a later
  phase.
- Reconciled only exact untouched legacy seed signatures to one home team.
  Locally edited team records are preserved.
- Added the PostgreSQL organisation foundation: units, bounded closure,
  immutable topology revisions, one-effective-membership exclusion,
  action-specific grants, delivery profiles, capability coverage, authority
  epochs, checkpoints and findings.
- Added atomic, idempotent legacy reconciliation with source digests,
  end-dating, audit and outbox evidence. Explicit `shadow` mode now runs this
  projection at startup. It remains non-authoritative and active mode still
  fails closed.
- The ordinary full suites passed with 1,873 backend tests collected and the
  frontend at 98.69 per cent line and 95.05 per cent branch coverage. Real
  PostgreSQL migration, integrity, reconciliation and shadow-startup tests
  passed separately. Phase 3 began only after these boundaries were in place.

## 2026-08-03 Hierarchical workforce Phase 3 foundation

- Added action-specific direct and descendant grant evaluation, bounded
  delegation lineage, versioned create/revoke grant commands, idempotent
  replay, database-clock validity, authority epochs and transactional
  audit/outbox evidence. Active hierarchy mode remains blocked until the
  complete Phase 3 administration and cutover gates pass.
- Added source provenance to legacy-projected units and delivery profiles.
  Reconciliation now retires removed source teams, memberships and capability
  coverage without changing manually created hierarchy records, and it rejects
  attempts to take over a manually owned identity.
- Added the canonical, versioned `team_task_ownership` PostgreSQL boundary for
  one receiving team or triage owner per ticket workflow leg. This is not yet a
  board and does not replace the live ticket state machine.
- Real PostgreSQL tests prove migration to revision `20260803_0019`, removed
  team retirement, manual-unit preservation, grant lifecycle integrity and
  stale-write rejection for task ownership.
- The full backend regression run passed 1,897 tests with one intentional
  N-1 compatibility skip. Targeted authority branch tests then raised the
  combined evidence to 98.26 per cent line and 95.01 per cent branch coverage.
  The frontend passed at 98.69 per cent line and 95.03 per cent branch
  coverage, followed by TypeScript, ESLint, Prettier and production build.
- Added the one-shot empty-install bootstrap ceremony. It requires an active
  platform administrator, recent reauthentication and a deployment-supplied
  nonce, then creates the first root, immutable topology evidence and explicit
  action ceilings in one serialisable transaction. Concurrent or later
  attempts fail closed and the denial is audited without storing the nonce.
- Added actor-bound preview and idempotent execute commands for child-unit
  creation and non-structural metadata edits. PostgreSQL rechecks the exact
  scoped grant, expected versions and material change under lock, retries one
  serialisation conflict, and writes command, epoch, audit and outbox evidence
  atomically. These commands are not yet exposed through the application UI.
- Advanced the migration head to `20260803_0021` for bootstrap state and
  organisation unit command records.
- Completed the remaining internal Phase 3 command foundation through
  migration `20260803_0027`: safe subtree reparent, single-home membership and
  exact-boundary personnel transfer, dependency-aware deactivation, nested
  merge and exact-disposition split. Each command is actor-bound, versioned,
  idempotent, serialisable and writes audit/outbox evidence in its transaction.
- Added a distinct PostgreSQL-only `management` mode. It wires organisation
  administration without reconciling legacy flat teams and without making the
  hierarchy authoritative for access, routing, calendars or workflow.
  `active` mode remains blocked.
- Exposed administrator-only, CSRF-protected APIs for bootstrap, unit
  lifecycle, grants, membership, transfer, deactivation, reparent, merge and
  split. Bootstrap additionally reauthenticates the current password, applies
  authentication throttling and requires the deployment setup nonce; neither
  secret is persisted, returned or copied into audit evidence.
- Added the first organisation administration workspace. It is reachable from
  Governance and Admin, progressively expands the hierarchy, inspects explicit
  grants, offers the one-time protected bootstrap, and freezes a server impact
  preview before create/edit confirmation. It explicitly reports that
  operational routing is unchanged. Restructure/workforce controls and cutover
  evidence remain before Phase 3 can close.

## 2026-08-01 Retrieval administration and index reliability

- Reworked Search and embeddings into the same provider, credential, model,
  test and apply hierarchy as the AI provider panel, while preserving its
  independent key and external-egress boundary.
- Made connection testing candidate-scoped so a successful offline mock probe
  cannot be mistaken for a Gemini test or authorise an untested selection.
- Replaced timestamp-sensitive corpus identity with a canonical content hash,
  generated truthful deterministic demo assets and preserved timestamps on
  unchanged seed upserts.
- Scoped ticket text and vectors to one generation, made PostgreSQL promotion
  atomic, preserved the previous winner on failure and recovered interrupted
  process-local builds at startup.
- Added API, UI, repository, migration and real PostgreSQL regression coverage
  for the new lifecycle. Live demo cleanup and final quality-gate evidence are
  recorded when the remediation is completed.

## 2026-08-01 Confirmed conversational interpretation and retry hardening

- Extended deterministic intake parsing for named, whole-year and relative date
  windows, then added transcript-derived guidance so unresolved answers do not
  trigger an identical question loop.
- Added an admitted model fallback for unresolved priority and date wording.
  It receives only the active current answer, target and current date, is capped
  at 4 KiB, and never receives prior history, other voice answers or stored
  intake.
- Kept model output non-authoritative. Exact-key, exact-evidence and closed-value
  validation produces application-owned confirmation copy; only the customer's
  later yes applies the suggestion. Free text, completeness, lifecycle,
  authorisation and submission remain deterministic.
- Hardened voice grouping, end-intent handling, stale confirmations, priority
  negation, provider admission fallback, valid abstention, circuit behaviour and
  provenance token bounds through independent security and code-quality review.
- Verification completed with 1,646 backend tests passing and 81 PostgreSQL-only
  tests skipped in the local non-PostgreSQL run. The 129-test focused boundary
  suite passed at 98.52 per cent combined line and branch coverage; Ruff, mypy,
  documentation links, diff checks and the 350-line source limit also passed.

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

## 2026-07-23 Documentation accuracy and navigation

- Audited current guides, runbooks, plans, component READMEs, specifications,
  ADRs and threat models against routes, permissions, settings, migrations,
  workflows and integrated security evidence.
- Added complete linked indexes and an explicit authority/lifecycle model for
  current guidance, acceptance contracts, decisions and historical evidence.
- Corrected persistence, dual search, audit, role, product-upload, reset,
  air-gap, infrastructure and release-gate guidance.
- Hardened exact-SHA air-gap packaging, per-image SBOM evidence and recursive
  transfer manifests against ignored, hidden and linked artefacts.
- Expanded the documentation gate to every Git-known Markdown file and local
  GitHub-style heading anchor.
- Added an Architecture Atlas with 32 accessible Mermaid views across users,
  workspaces, workflow hand-offs, components, data, search, AI authority,
  security, deployment, CI, observability and recovery.
- Corrected the browser-to-API, workflow, dual-index, GCP KMS, local
  notification and recovery boundaries against implementation.
- Added repository-wide Mermaid parsing to local checks and Backend CI.

## 2026-08-01 Numbered local evaluation logins

- Added a Compose-only login profile that maps the 16 synthetic seed identities
  to `admin1` through `admin16` with the deliberately weak local password
  `admin`; runtime validation rejects the profile outside `environment=local`.
- Made the persisted migration one-time and collision-safe. It preserves user
  IDs and authority, advances credential versions, invalidates old sessions and
  never exposes canonical seed names as alternate authentication identities.
- Preserved canonical seed references behind an internal-only resolver and
  reserved canonical, numbered and legacy names from registration.
- Repaired the persisted JIOC seed persona to the current Manager role through
  the audited admin API. Live checks proved all 15 active accounts, the disabled
  account block, canonical-name rejection, API readiness and an empty session
  store.
- The database-enabled backend gate passed 1,644 tests with one intentional
  compatibility skip and 97.79 percent total coverage. Ruff, mypy, line-limit
  and Docker image build checks also passed.
- Corrected the login form's obsolete email-only validation and made Compose
  derive the API hostname from the browser entry hostname. A live in-app
  browser pass proved `admin2` reaches the customer workspace from
  `127.0.0.1` with its session retained.
- The complete frontend gate passed 546 tests at 98.65 percent line and 95.08
  percent branch coverage; formatting, ESLint and TypeScript also passed.

## 2026-08-01 Customer request history and closure feedback

- Separated active work from collapsed closed history and replaced permanent
  multi-form feedback with a sequential, closed-ticket product prompt.
- Enforced `CLOSED_*` eligibility in the feedback service for both listing and
  submission. Active and cancelled requests are not feedback-eligible.
- Updated demo feedback timing while preserving immutable analytics and raised
  only the full Docker demonstration's retained-ticket ceiling to 500.
- Kept default and hosted limits unchanged and made principal denials describe
  the required close-or-cancel action accurately.

## 2026-08-01 Intake date clarification recovery

- Fixed a deterministic intake loop that ignored named and whole-year date
  ranges, retained `last year` as ambiguous prose, then refused a later valid
  correction because the time-period field was already populated.
- Added bounded local normalisation for numeric, named, whole-year and relative
  calendar windows. Concrete corrections now replace only unresolved date
  values, preserving an already valid range.
- Added regression coverage for the reported conversation and invalid or
  reversed ranges. The full backend run passed 1,579 tests with 81
  environment-gated skips; changed intake modules remain at 99 to 100 percent
  combined coverage.

## 2026-08-01 Retrieval administration and index integrity

- Reworked retrieval administration into a provider, model, test, apply and
  rebuild sequence. Connection evidence is now tied to the exact draft choice,
  and Gemini remains gated by its dedicated key and explicit egress consent.
- Made demo asset metadata truthful and seed upserts idempotent. Corpus hashing
  now uses canonical retrieval inputs and sorts unordered semantic terms, so an
  unchanged corpus remains current across Python process restarts.
- Scoped request documents to their index generation, made generation promotion
  atomic and added interrupted-worker recovery. The API container now packages
  its Alembic configuration, and Compose gates API startup on a successful
  one-shot migration.
- Hardened promotion against duplicate, mismatched and stale source identities.
  Bounded provider transport now prevents oversized or malformed Gemini
  responses from leaking upstream values through logs or exceptions.
- Backed up the local database, then removed only the two verified synthetic
  2,000-asset stress products. The mock index warning count fell from 4,057 to
  35 honest extraction warnings: 14 missing objects and 21 unsupported types.
- Rebuilt generation 3 over 197 products, 861 passages and 21 indexed request
  vectors. It remained ready after an API restart with corpus version
  `ebf931b0e1470d4b8a616052`.
- The PostgreSQL backend gate passed 1,746 tests with one compatibility skip at
  98.33 percent line and 95.55 percent branch coverage. The frontend gate
  passed 550 tests at 98.67 percent line and 95.08 percent branch coverage.

## 2026-08-02 Synthetic Ukraine-Russia report expansion

- Audited the live Store before expansion: it held 217 products and 193 PDF
  assets. All 144 original deterministic corpus PDFs had valid integrity
  metadata, object bytes and an indexed asset state, but the 45 Russia reports
  used generic exercise areas and did not cover Ukraine-war search scenarios.
- Added 72 deterministic four-page PDFs across 12 clearly synthetic scenarios:
  Kursk, northern Donbas, Donetsk, Luhansk, Kharkiv, Zaporizhzhia, Kyiv missile
  and drone activity, Black Sea activity, Moscow drone and air-defence activity,
  and Donbas electronic warfare. Coverage periods span 2025 and 2026.
- Improved generated narratives and long-region wrapping. Visual checks of all
  four report pages and representative covers found no clipping, overlap or
  unreadable text after two repair passes.
- Seeded the existing database idempotently. The live Store now holds 289
  products, including 72 new reports, without removing 28 existing non-seed
  records. Generation 4 is ready over 269 eligible products, 1,221 passages and
  21 request vectors; all 72 expansion assets contributed 288 indexed pages.
- Exercised an authenticated download grant and confirmed HTTP 200,
  `application/pdf`, attachment and `no-store` headers, a valid PDF signature,
  four pages, a matching SHA-256 hash and visible mock banners.
- Live Store queries returned expansion products first for every requested
  location and capability. The complete PostgreSQL backend gate passed 1,747
  tests with one compatibility skip at 98.34 percent line and 95.56 percent
  branch coverage. Ruff, mypy, Bandit, architecture, documentation, Mermaid and
  file-size checks also passed.

## 2026-08-02 Synthetic provenance and local provider presentation

- Replaced repeated page-level `MOCK DATA ONLY` warnings with one persistent,
  accessible `Synthetic exercise` indicator in the authenticated command bar.
- Renamed the user-facing offline text and retrieval implementations to Local
  assistant and Local search while preserving their stable internal identifiers.
- Moved raw retrieval provider, model, corpus and release identifiers into a
  collapsed technical disclosure and kept external activation explicit.
- Removed warning prefixes from seeded titles and descriptive prose. Product
  handling metadata remains fixed and each generated PDF page retains one clear
  synthetic marker.
- Added startup convergence for the original baseline Store records, translated
  the legacy signals product type and suppressed internal provenance tags from
  prominent Store chips while retaining them for retrieval compatibility.
- The complete gates passed: 551 frontend tests at 98.67/95.11 line/branch and
  1,748 PostgreSQL backend tests with one intentional skip at 98.34/95.56.

## 2026-08-02 Automatic retrieval and richer exercise products

- Activated verified Gemini search generation 8 over 269 products and 2,306
  passages, with automatic debounced rebuilds and zero asset failures.
- Repaired 14 objects, added bounded CSV, GeoJSON and image extraction, and
  expanded deterministic reports to eight visually verified operational pages.
- Retained sparse legacy-metadata fallbacks as regression coverage. Final gates
  passed: 1,765 backend tests and 118 frontend files at 97.88 per cent combined
  backend coverage and 98.67/95.05 frontend line/branch coverage.

## 2026-08-02 Customer search recovery and fulfilment outcomes

- Replaced stale customer-facing hybrid warnings with assurance-aware copy and
  retained non-definitive handling for partial zero-result searches.
- Added an owner-only, audited reject-all feedback flow with refined search,
  JIOC continuation and explicit successfully fulfilled or unfulfilled closure.
- JIOC retains sole authority for RFA, CM, clarification and human review.

## 2026-08-02 Documentation and screenshot refresh

- Re-captured every documented workspace from the current local application at
  the 1440 x 1000 desktop acceptance viewport, added JIOC oversight and Store
  product-detail coverage, and exposed a current screenshot gallery in the root
  README.
- Added a screenshot inventory with route, role and purpose metadata, plus a
  repeatable safety and visual-review policy for future interface changes.
- Corrected current guides to the 261-product fresh seed, 58 ACGs, persistent
  Synthetic exercise indicator, personal Store folders, collapsed product
  metadata, RFI return links and automatic post-migration index preparation.
- Exempted Markdown documentation from the 350-line source and configuration
  limit so reader structure, not an arbitrary code-size gate, determines how
  documentation is organised.

## 2026-08-02 Istari Intelligence Store browse experience

- Added a `sort` query parameter (`relevance|title|coverage`) to
  `GET /api/v1/store/products`, threaded through `StoreSearchFilters` into
  both the SQL browse path (static `ORDER BY` fragments selected by enum,
  never interpolated request text) and the Python hybrid path. Ordering is
  applied to the whole matched set before paging, so a sort choice now
  holds across pages; previously there was no sort parameter and the web
  UI reordered only the current page.
- Added `facets.counts`, giving the number of visible products behind each
  product type, region and tag, counted over the access-scoped,
  structurally-filtered set via `jsonb_agg` in `SEARCH_SUMMARY_SQL`. Hidden
  products contribute to neither the lists nor the counts. Counts were added
  alongside the existing ordered value lists rather than replacing them: the
  first attempt returned `{value, count}` pairs in place of the string lists,
  which the OpenAPI compatibility gate correctly rejected as a breaking
  response change.
- Extended the projection recheck to cover facets. A security review of this
  change found that the free-text search path returned SQL-derived facet
  values and counts without the `can_read` recheck the structured browse path
  already applied, so a divergence between the SQL scope predicate and the
  service policy could disclose a region, type or tag belonging to a product
  the requester cannot read, and now its count as well. Both paths now share
  one recheck and fail closed on drift; a regression test asserts a hidden
  product contributes to neither facet lists nor counts on either path.
- Added one-shot query relaxation: when a multi-term text query returns
  nothing, the service retries with the terms joined by `OR` and sets
  `relaxed: true` on the response. Match reasons are always derived from
  the query the operator typed, never the broadened form, and single-term
  queries are never broadened. Cause: `websearch_to_tsquery` requires every
  term, so natural phrases such as `arctic shipping routes` dead-ended
  despite strong partial matches.
- Moved applied Store search state into the URL (`q`, `type`, `region`,
  `tag`, `source`, `from`, `to`, `sort`, `page`) via a new `useStoreSearch`
  hook, so a search now survives navigation, refresh, bookmarking and the
  browser Back button; it was previously component state, lost whenever a
  product was opened.
- Raised page size from 6 to 24 with numbered pagination (first, last and
  a window around the current page), and added a `StoreFacetRail` that
  turns facets into clickable filters with counts; region and tag facets
  were previously fetched and discarded, and product-type facets were
  inert chips.
- Added a `StoreResultCard` that leads with classification marking and
  status badge, renders coverage windows as plain dates and shows the
  product's asset make-up, with draft products badged. Match explanations
  were rewritten into plain language (for example `Matched arctic`), with
  the raw retrieval signals kept as secondary detail.
- Requested owner-team scoping (`My Products`, RFA/Collection product
  workspaces) from the server instead of filtering a returned page
  client-side, removing the totals/pagination inconsistency the old
  client-side filter required workarounds for. Collapsed the personal
  library panel to a single compact bar instead of it occupying the top of
  the workspace.
- Fixed an out-of-range page (for example a bookmarked `page=3` on a
  result set that had shrunk), which previously rendered
  `Showing 49-17 of 17`; it now explains the page is past the end and
  offers a return to the first page. Made `Back to store` return to the
  operator's applied search, rebuilt from known store parameters only so
  navigation state stays presentation-only and cannot carry arbitrary
  content into the link.
- Hid facet counts while a search term is applied. Refinement options are
  computed without the term so a narrow search still leaves somewhere to go,
  which means their counts describe the catalogue, not the results on screen.
  Refreshing the documentation screenshot exposed the consequence: the rail
  read `Assessment report 136` beside `12 products`. The options stay, so the
  ADR 0017 behaviour is unchanged, but the contradictory number does not.
- Added real-PostgreSQL coverage for the new SQL. The default suite runs the
  memory persistence provider, so the Python ranking path answers every browse
  query and the new `ORDER BY` variants and `jsonb_agg` facet aggregation were
  never executed by a test. `tests/postgres/test_store_sort_and_facets_sql.py`
  now seeds products against a real database and asserts newest-coverage-first
  ordering with undated products last, title ordering, an executable statement
  for every `StoreSortOrder` member, and facet counts covering the whole
  filtered set rather than the returned page.
- Deleted the superseded `StoreSearchFiltersPanel.tsx` and
  `store-match-reasons.css`. Updated
  `docs/specs/store-hybrid-browse-search.md` (sort order, facet counts,
  broadened queries and web search state) and the Intelligence Store
  section of `docs/USER_GUIDE.md`.
- Verified with the combined backend suite of 1,714 unit tests and 82
  PostgreSQL tests passing at 98.32/95.41 line/branch coverage, 608
  frontend tests passing at 98.71/95.27, and clean Ruff, mypy, Bandit,
  ESLint, Prettier, TypeScript, architecture-boundary, file-length and
  OpenAPI contract checks. Confirmed end to end against the local
  279-product Docker catalogue.

## 2 August 2026 Intelligence Store projects and subscriptions

- Reframed the Store as four clear workspaces: catalogue discovery, a private
  Library, collaborative projects, and private search subscriptions. This keeps
  personal organisation separate from shared research and avoids turning the
  Store into another dense dashboard.
- Added scoped projects with a written purpose, optional geographic and date
  bounds, owner-managed membership, authorised product collections, working
  notes, intelligence questions, archive/restore and an attributable activity
  record. Product visibility and product-identifying activity are recalculated
  for every viewer, so project membership never grants product access.
- Added private reusable search subscriptions rather than alerts. A user can
  carry a Discover query into a named manual, daily or weekly review, open its
  current results, pause it or delete it. No email, push delivery or cached
  result set was introduced.
- Added direct My Library, Projects and Subscriptions routes, a safe return from
  product detail to the originating project, and a product-detail action for
  adding a visible product to an active project.
- Recorded the product contract, ADR 0048 and the extended Store threat model.
  Scheduled execution, generated briefings, mapping and workflow tasking stay
  explicit future work.
- Verified 1,814 backend tests with one intentional compatibility skip against
  real PostgreSQL at 98.36 per cent line and 95.44 per cent branch coverage.
  All 628 frontend tests passed at 98.73 per cent line and 95.03 per cent branch
  coverage, alongside the static, contract, documentation and production-build
  gates.

## 3 August 2026 access-controlled ACG subscriptions

- Extended subscriptions from catalogue-wide saved searches to optional,
  explicit ACG scopes. The selector contains only the user's active ACG
  memberships and supports up to 12 groups per subscription.
- Kept ACG selection restrictive rather than authoritative. The API validates
  membership when criteria are created or changed, and Store search intersects
  the saved selection with the user's current visibility scope. Tampered,
  inactive and revoked ACG identifiers fail closed.
- Made subject tracking clearer for non-technical users with a dedicated ACG
  selector and plain-language keyword guidance. Keywords and phrases can be
  combined with region, product type, tag, source type and coverage dates.
- Added an access-changed state so a subscription does not offer stale results
  after one of its selected ACG memberships is removed.
- Updated the feature contract, ADR 0048, Store threat model, OpenAPI contract
  and user guide, with backend and frontend access-regression coverage.
- Verified 1,816 backend tests with one intentional compatibility skip at
  98.37 per cent line and 95.47 per cent branch coverage, including disposable
  PostgreSQL database tests. The full frontend suite passed at 98.73 per cent
  line and 95.07 per cent branch coverage.

## 3 August 2026 Sprint 24 hierarchy administration foundation

- Corrected legacy flat-team availability, assignment bounds and process-wide
  mutation locking before allowing hierarchy to influence any live workflow.
- Added the PostgreSQL organisation shadow, closure and immutable topology
  history, single-home membership exclusion, delivery profiles, capabilities,
  authority epochs, reconciliation checkpoints and source-safe legacy replay.
- Added explicit action grants with bounded delegation, one-shot empty-install
  bootstrap and previewed, idempotent create and edit commands. Each command
  rechecks the exact grant and aggregate version in its serialisable commit.
- Added safe subtree reparenting. The preview binds topology and affected
  membership, grant, capability and active-task state to the actor. Execution
  moves the complete subtree, writes a revision for every changed path and
  refuses cycles, excessive depth, stale state or silent destination-grant
  expansion.
- Added previewed membership create, update and immediate-end commands. Active
  account, delivery-team eligibility, exact roster-management authority, unit
  and membership versions are rechecked before the database mutation. The
  PostgreSQL exclusion constraint and user-scoped serialisation enforce one
  non-overlapping home membership.
- Added scheduled personnel transfer commands. Scheduling leaves the source
  membership untouched. At the exact boundary the activation worker rechecks
  the account, both endpoint grants, the source membership, destination and
  complete membership timeline, then ends the source and creates the target in
  one transaction. A failed activation is marked blocked and retains the old
  home membership, so there is neither a cross-posting nor an unintended gap.
- Added fail-closed unit deactivation. Only an empty, active non-root unit can
  be end-dated. Active descendants, memberships, direct grants, delivery
  profiles, capability coverage, task ownership or pending personnel transfers
  block the command until each dependency is explicitly resolved. Identity,
  closure and topology history remain available after deactivation.
- Added the minimal canonical workflow-leg team ownership boundary. Active
  hierarchy mode remains deliberately unavailable until the remaining Phase 3
  lifecycle commands, administration API, UI and cutover evidence are complete.
- Added the explicit-disposition organisation merge command. It safely merges
  two or more non-overlapping active source subtrees into an existing distinct
  successor and rejects roots, nested successors, overlapping sources,
  incomplete disposition sets, conflicting delivery profiles, excessive
  resulting depth, silent destination-grant broadening and stale dependency
  state. Every direct child is a named disposition; its complete subtree is
  reattached and receives immutable revisions for every changed path.
  Membership moves end the source posting and create one replacement posting,
  preserving the no-cross-posting invariant. Grants are explicitly revoked,
  active tasks are moved or cancelled, pending personnel transfers are
  cancelled and source units are end-dated in the same serialisable transaction.
- Added immutable version history for team task ownership, delivery profiles
  and capability coverage before restructure updates. Audit and outbox evidence
  contains bounded identifiers, counts, state and reason hashes rather than the
  free-text reason. Direct store calls revalidate the complete disposition set,
  scoped grant lineage and actor-bound preview rather than trusting the service.
- Focused unit and disposable PostgreSQL tests cover bootstrap concurrency,
  create/edit replay and revocation, subtree movement, direct closure tampering,
  stale reparent previews, destination-scope broadening, merge replay,
  history preservation, pending-transfer cancellation and atomic rollback on
  a late dependency. Closure-tampering tests also prove that replaying an old
  merge command identifier cannot authorise later deletion. Alembic head is now
  `20260803_0026`.
- Added the split contract and policy foundation. A request defines one current
  source, its current parent, at least two unique successor units and separate
  restructure-grant evidence for both existing units. The preview inventory
  names every child, membership, grant, delivery profile, capability mapping,
  active task and pending transfer. Every record must have one current,
  kind-safe mapping to a declared successor or an allowed terminal action.
- Added revision `20260803_0027` for split command/disposition evidence and a
  closure guard that recognises only a current transaction's recorded child
  mapping. The split executor creates all declared successors, moves complete
  named child subtrees, replaces or ends memberships without cross-posting,
  revokes grants, moves or ends delivery policy, moves or cancels tasks and
  cancels pending transfers atomically. Fixed-term and scheduled postings keep
  their time bounds, future postings selected for termination are cancelled,
  and scheduled grants are revoked no earlier than their valid-from time.
- Disposable PostgreSQL evidence covers successful dependency movement,
  immutable task/profile/capability history, topology revision and closure
  integrity, idempotent replay, stale-preview rollback, successor conflicts and
  scheduled-record handling.
- Exposed the hierarchy command plane only in non-operational `management`
  mode through administrator, session and CSRF-protected APIs. Added current
  unit and membership reads without exposing membership reasons or provenance.
  Bootstrap requires current-password reauthentication and a deployment setup
  nonce, with generic failure responses and no secret logging.
- Added the Organisation management workspace. It now supports hierarchy
  navigation; unit create/edit/reparent/deactivation; named grant delegation
  and reasoned revocation; current roster additions, edits and removals;
  scheduled single-home transfers; and merge/split dependency assessment,
  explicit dispositions and exact reviewed-plan execution. The interface
  continues to state that operational routing is unchanged. Scoped manager
  views and authority cutover remain gated.
- Started the non-authoritative canonical calendar slice. Alembic revision
  `20260803_0028` adds event, scope, recurrence-exception, immutable-history and
  actor-bound command tables, plus database triggers that require cancellation
  instead of deletion and prevent history rewrites.
- Added personal and manager-source calendar policy with exact previews,
  serialisable event/owner/idempotency locks, replay collision detection and
  transaction-time revalidation of manager grant lineage and the subject's one
  current home membership. Audit and outbox records contain bounded identifiers
  and reason hashes, never calendar notes.
- Added authenticated calendar APIs, a seven-day profile snapshot and a full
  90-day personal agenda. Users can add and cancel their own all-day activity;
  changes refresh the shared canonical query rather than copying team entries.
  The same canonical records now project into privacy-safe direct-team rows and
  root-level descendant daily aggregates. Aggregate and detail are separate
  grant actions; direct teammate timing is coarsened; descendant views contain
  no person rows; and cohorts below five, unavailable counts from one to four
  and truncated result sets are suppressed. The organisation inspector keeps
  this view collapsed by default and requires an explicit detail request.
  Working patterns, legacy migration, recurrence editing, child-level
  complementary suppression, the ordinary manager workspace and capacity
  integration remain gated.
- Enabled the existing non-operational `management` mode in local Compose so
  the organisation command surface and canonical personal calendar can be
  exercised. This mode does not replace routing, access or workflow authority.
- Focused verification now passes 34 backend calendar, hierarchy and workforce
  authority tests. Eight tests also pass against disposable PostgreSQL,
  covering migration history, event lifecycle, replay, tombstones, immutable
  history and audit-note redaction. The complete frontend suite passes the
  repository gate at 98.74% lines, 95.20% functions and 95.03% branches.
- Added interaction and failure-path coverage for every organisation workspace
  transition, grant filtering, roster changes, transfer safeguards, timed and
  unavailable calendar entries, sparse product metadata and controlled-asset
  denial. This closed the coverage gap without weakening the 95% thresholds.
- Added exact-action and transaction-time calendar projection evidence,
  including a disposable PostgreSQL test proving that aggregate authority
  cannot be reused for detail. The complete frontend suite passes at 98.73%
  lines, 95.17% functions and 95.02% branches after adding direct, descendant,
  detail, empty and failure-state projection journeys.
- Added an ordinary-user organisation workspace query under a repeatable-read
  PostgreSQL snapshot. It returns one current home posting and separately
  deduplicated managed roots, with no role or administrator bypass. Managed
  metadata requires independent `organisation:view` plus `workspace:view`;
  calendar capability hints require their exact actions and descendant flags
  are the intersection of both hierarchy actions. The normal Team page now
  presents My team and Managed teams separately and quietly retains the legacy
  workspace when hierarchy management is disabled.
- Closed the canonical ownership gap for new analyst assignments. Relational
  assignment now locks the expected ticket and commits its active workflow-leg
  team owner, current topology/profile versions, audit event and outbox event in
  one transaction. A changed or inactive delivery authority rolls everything
  back with a safe retry response.
- Added the first operational board slice to the normal Team workspace. It is a
  read-only direct-team projection protected by exact `task:view` lineage,
  hides completed work by default, caps results at 100 and returns only an
  allowlisted card summary. The UI groups those cards by the existing workflow
  state without introducing drag-and-drop or a parallel state machine.
- Added automatic historical assignment reconciliation for management mode.
  A digest-addressed checkpoint scans a bounded active corpus and backfills
  canonical ownership only for routes with one explicit team ID and current
  matching delivery authority. Missing, conflicting or ambiguous ownership is
  preserved as a blocking finding for manual disposition, never guessed from
  personnel names, team labels, roles or route-wide queues.
- Added migration 0029 for canonical enhanced work packages and conserved
  capacity. It introduces accountable participants, contributors,
  within-task dependencies, immutable package history, working patterns,
  capacity exceptions and idempotent personal reservations without creating a
  second ticket state machine.
- Extended the relational assignment transaction to project each ticket work
  package with one accountable analyst from the explicit assignment. The
  transaction locks and rechecks that each candidate has one eligible current
  home posting in the owning leaf delivery team. Package status changes append
  canonical history and release active reservations on completion.
- Added overlap-safe 15-minute capacity arithmetic and an internal PostgreSQL
  reservation store. Per-user advisory locking, package versions, current home
  posting, working pattern, calendar availability, existing reservations,
  capacity exceptions and remaining package effort are checked before insert.
  Reusing an idempotency key with another request fails closed. The internal
  store remains outside the HTTP surface until assignment authority and full
  recurrence/all-day expansion are joined to the planning command.
- Expanded the public-safe identity catalogue from 16 to exactly 53 unique
  fictional personas while preserving the original numbered login positions.
  The cohort now has exactly 24 generic Intelligence Analyst accounts. Seven
  compatibility delivery teams distribute them once each as 14 RFA-only and
  ten CM-only analysts, with no cross-posted analyst. This is the identity and
  flat-fixture slice only. Fresh seed user and team identities are now stable,
  namespace-derived IDs, and a machine-readable report detects count,
  duplicate, cross-post and active-leaf staffing drift without rewriting local
  data. Transactional relational application, competencies, calendar/workload
  scenarios and the complete drift report remain gated.
- Added an explicit relational exercise manifest for Defence Intelligence,
  DI Joint User, DI NCGIA, MIS, UKSF, SAS, SBS, SRR, 18SR, 14SR, PAGC and
  4 RANGERS, plus four RFA and three CM delivery leaves. The parentage is
  deliberately encoded as a synthetic construct and makes no real-world
  organisational claim. Every one of the 53 personas has one posting; analyst
  lifecycle rows produce exactly 12 active eligible RFA and nine active
  eligible CM analysts, one future joiner, one ended former analyst and one
  suspended analyst. All 24 analysts have stable working-pattern records,
  including one part-time scenario.
- Added the protected relational fixture ceremony for that manifest. The
  administrator first receives a conflict-first preview, then reauthenticates
  to commit the exact reviewed state. The serialisable PostgreSQL command uses
  stable fixture identifiers, resolves current seed user IDs by canonical
  username, creates only missing records, journals replay and emits bounded
  audit/outbox evidence. A foreign root, edited fixture row, local profile,
  posting overlap, working-pattern overlap or missing/inactive identity blocks
  the whole transaction. No local row is updated or deleted. The Organisation
  admin workspace exposes the same preview, clear counts, conflict list and
  password-confirmed apply flow. Four backend policy/API tests and five focused
  organisation frontend journeys pass. Disposable-PostgreSQL tests now prove
  full apply, exact replay, settled preview by a second administrator and
  rollback on a foreign-root conflict.
- Extended the relational manifest with controlled capability evidence rather
  than descriptive-profile inference. Migration 0031 adds a verified analyst
  competency ledger. Seven delivery leaves receive 21 team capability rows and
  all 24 analysts receive exactly two competencies aligned to their one home
  team. A machine-readable relational integrity report now checks exact counts,
  stable-ID uniqueness, leaf staffing and competency alignment. The same
  previewed transaction also creates eight bounded canonical calendar
  scenarios with scope, immutable initial version and creation-command
  evidence, including leave, training, duty, partial availability, a
  manager-created commitment and a private appointment.
- Added 82 stable least-privilege fixture grants for area managers, leaf leads
  and bounded JIOC, QC, Store and platform roles. Added 24 operational task
  aggregates, 24 canonical workflow-leg ownership rows and 48 two-stage work
  packages. The dataset spans every delivery leaf, active board states, urgent
  and blocked work, analysed CM handover and three recent closed examples.
  Dependencies, accountable participants, immutable histories and idempotent
  commands are included, while any stable-ID, reference or evidence collision
  aborts the additive transaction.
- Made capacity reservations understand canonical all-day absence. Civil dates
  are expanded at midnight in the event's validated IANA time zone and then
  intersected with working time. Recurrence remains fail-closed, preserving the
  activation gate without treating ordinary leave as unknown capacity.
- Bound capacity reservation identity and replay to the acting manager. The
  PostgreSQL transaction now validates current scoped `task:assign` lineage for
  both first execution and replay. Cross-actor idempotency reuse is rejected,
  with real-PostgreSQL evidence for an authorised leaf lead and an unauthorised
  customer.
- Added canonical My Work as an actor-only package projection. Active
  accountable and contributor participation is joined to matching package,
  workflow-leg ownership and ticket aggregate evidence in one repeatable-read
  transaction. The bounded API uses deterministic keyset paging, recent-only
  opt-in completion and a privacy-minimised response. Analysts now see their
  first five active packages on their profile and can open the established
  authorised task route. Real PostgreSQL evidence covers accountable and
  contributor rows, paging and isolation from a non-participant customer.
- Added an aggregate direct-team capacity forecast for managers with exact
  current assignment authority. It combines working patterns, unavailable
  calendar time, capacity reductions, active reservations and policy buffers
  over a maximum 31-day interval, while unknown identity or workforce evidence
  remains explicit. The task board presents the next seven days in plain
  language and does not expose analyst identities, calendar notes or exclusion
  causes. Disposable PostgreSQL evidence proves the forecast against the full
  synthetic workforce; atomic planning remains the final decision gate.
- Removed the forecast's split identity read. Alembic revision 0032 introduces
  a password-free account projection with only user ID, active state, roles,
  credential version and a consistency hash. PostgreSQL account persistence
  updates the encoded snapshot and projection in one transaction, deletes
  removed identities and rejects malformed or duplicate snapshots. Capacity
  now evaluates active Analyst eligibility inside its repeatable-read database
  transaction; missing projection evidence remains unknown. Focused unit and
  API tests passed, and isolated PostgreSQL tests proved migration, account
  deactivation synchronisation and the full synthetic capacity projection.
- Added the Phase 8 JIOC relational shadow context without changing active
  routing. The synthetic fixture maps all 40 catalogue team IDs to one of seven
  delivery leaves and gives the stable internal JIOC principal only a
  revocable `recommendation:view` descendant grant. One repeatable-read query
  combines mapped teams, projected active Analyst roles, single-home postings,
  working patterns, calendars, exceptions and reservations, retaining only
  candidate ID, status and aggregate assignable minutes. Composition requires
  both organisation `management` and routing `shadow`; active mode is proven to
  retain the legacy evaluated context. The routing gate now has 24 labelled
  safety cases and 24 exact replay partners, with replay mismatch itself a
  release failure. Focused routing tests and isolated PostgreSQL fixture tests
  pass. Independent approval remains deliberately open.
- Completed the broad regression pass for this milestone: 2,027
  non-PostgreSQL tests passed, followed by 132 PostgreSQL tests with one
  intentional compatibility skip. Migration journeys cover empty, legacy,
  runtime-bootstrapped, downgrade/re-upgrade and reverse-projection databases
  through revision 0032. Combined coverage is 97.69 per cent line and 93.0 per
  cent branch. Every new JIOC/identity module is at 100 per cent line and
  branch coverage, but the repository-wide branch gate remains below the
  required 95 per cent because of uncovered branches in the broader Sprint 24
  organisation, calendar and package-planning slices. The threshold was not
  changed and cutover remains blocked on closing that test debt.
- Closed the Sprint 24 repository-wide coverage debt without changing runtime
  behaviour or lowering a threshold. New fail-closed tests exercise every
  material branch in organisation lifecycle, reparent, merge, transfer,
  membership and deactivation persistence; workforce-calendar policy and
  PostgreSQL mutation boundaries; work-package planning and capacity forecasts;
  projection drift; synthetic-fixture replay; personal-work accountability;
  and team-board package decoding. A fresh authoritative run passed 2,130
  non-PostgreSQL tests and 137 PostgreSQL tests, with one intentional
  compatibility skip, at 98.22 per cent line and 95.35 per cent branch
  coverage. Ruff formatting and lint, strict mypy, the 350-line limit,
  architecture boundaries, documentation links, Mermaid parsing, security
  policy, OpenAPI compatibility, frontend type checking, ESLint, Prettier and
  the full frontend test suite all pass. Coverage is no longer a cutover
  blocker; independent approval, browser journeys and bounded authority-cutover
  evidence remain open.
- Enforced grantor-account authority at the PostgreSQL commit boundary. Every
  human grant holder and recorded human grant creator in a lineage is locked in
  deterministic order against the minimal account projection and must still be
  active. Missing or suspended people invalidate the chain immediately; only
  the code-registered JIOC service principal is classified as a service. Real
  PostgreSQL evidence covers holder, upstream/root creator, missing-account and
  concurrent-suspension cases.
- Gave the expanded relational-capacity/replay evaluation its own unapproved
  release identity. The established v2 release remains the sole local default,
  so legacy approval cannot make the new 48-case report active-ready.
- Added migration 0033 and reviewed contributor add/end commands. The
  serialisable operation binds package, ownership, exact `task:assign` grant,
  current account and sole eligible home-posting evidence; forbids accountable
  owner duplication and cross-posting; writes immutable history, command,
  audit and outbox evidence; replays idempotently; and removes ended work from
  My Work immediately.
- Added a mutation-free cutover-readiness endpoint and admin panel. A bounded
  repeatable-read snapshot returns only safe codes, statuses and counts for
  migration, topology, identities, reconciliation, ownership, packages,
  reservations, routing mappings and the scoped JIOC service grant. External
  routing approval, browser, CI and security artefacts remain blockers. The UI
  explains this in plain language, collapses technical details and contains no
  activation control.
- Re-ran the authoritative gates after these slices: 2,162 non-PostgreSQL tests
  and 142 PostgreSQL tests passed with one intentional skip. Combined backend
  coverage is 98.23 per cent line and 95.38 per cent branch. The full frontend
  suite, TypeScript, ESLint and Prettier pass; Ruff, strict mypy, line limit,
  architecture, documentation links, Mermaid, security policy and OpenAPI
  compatibility also pass. Active organisation authority and the new routing
  context remain disabled pending demand estimates, independent approval,
  browser evidence, repair/runbooks and bounded cutover proof.
- Added migration 0034 and reviewed work-package dependency add/remove
  commands. Preview and execution bind exact package, ownership, graph and
  `task:assign` lineage versions; restrict links to active packages in the same
  ticket, workflow leg and leaf; reject self-links, duplicates, absent removals
  and cycles; and fail closed beyond 128 packages or 512 edges. The
  serialisable write advances immutable package history, command, audit and
  outbox evidence atomically. Focused verification passed 25 unit/branch tests,
  one real-PostgreSQL lifecycle, two migration journeys and 15 route/security
  regressions.
- Added migration 0035 and a safe administrator-only legacy-calendar import.
  The actor-bound preview/apply flow uses stable UUIDv5 canonical identities,
  preserves ownership, creator, team, dates, status and notes, and excludes
  note text from history, audit and outbox evidence. Invalid, orphaned or
  colliding rows become blockers. Apply is serialisable and idempotent, with no
  deletes, overwrites, dual writes or cutover. Thirty-three focused tests pass,
  including real PostgreSQL proof that imported unavailability changes the
  canonical capacity forecast.
- Added a dedicated management-mode real-PostgreSQL browser suite. Seven
  journeys prove read-only cutover blockers, private calendar isolation,
  analyst My Work, direct-manager board/capacity/planning access, ancestor
  suppression and detail denial, JIOC visibility without assignment authority,
  and QC queue continuity. The suite also exposed an existing secure-workflow
  assignment regression for separate repair before end-to-end release evidence
  can be claimed.
- Fixed that assignment regression without weakening canonical authority. The
  compatibility delivery-team seeds now reuse the canonical manifest IDs, and
  assignment ownership/package projection is composed only when organisation
  mode is `management` or `active`. Disabled mode therefore retains the
  established workflow instead of requiring non-authoritative organisation
  rows. Focused checks passed 70 non-PostgreSQL and four PostgreSQL tests, and
  the secure real-PostgreSQL browser workflow passed all ten journeys from
  assignment through manager approval, QC release and download.
- Added the bounded whole-series recurrence vertical for canonical personal
  calendars. Daily and weekly activity now has one DST-safe expansion shared by
  personal, team, descendant aggregate, forecast and reservation readers. API
  occurrences expose stable series and occurrence identities while commands
  retain series versioning and idempotency. The personal editor supports
  accessible creation, whole-series editing and confirmed cancellation.
  Stored exceptions fail closed; edit-this, edit-future and exception handling
  remain explicit later work.
- Added the Phase 6 workspace-productivity vertical: actor-owned saved board
  views, manager-authorised package templates, an idempotent privacy-minimised
  work-update inbox, acknowledgement and delivery preferences. Opaque task and
  package links to Store projects/products validate independent Store policy at
  creation and every projection, so revocation hides links without merging
  either authority model. The UI keeps these secondary tools collapsed until
  requested. Unit, API, accessibility and real-PostgreSQL journeys cover the
  principal flows and current-authority revocation.

## 2026-08-04: package lifecycle and capacity reconciliation

- Added atomic contributor capacity reservation and release, with active
  participant and single-home authority checks.
- Added explicit cancel, unlink or replace dispositions before cancelling a
  package that has dependants, including bounded acyclic graph validation.
- Added migration 0042 lifecycle controls for package/ticket termination, hold,
  rework, reassignment and workforce eligibility changes. Planning-input and
  calendar changes now raise explicit review conflicts.
- Extended historical ownership reconciliation to backfill missing packages
  without overwriting existing package decisions.
- Added real PostgreSQL one-winner evidence for competing reservations and
  opposite dependency edges.
