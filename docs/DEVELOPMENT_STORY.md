# Coeus Development Story

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
