# Coeus Master Implementation Plan

The authoritative project implementation plan is
`coeus_spec_driven_implementation_plan.md` at the repository root. This file is
the concise delivery tracker and must stay within the repository line limit.

## Current Stage

Sprint 15 implementation and Sprint 16 are delivered; Sprint 15's full-role
browser acceptance evidence is carried into Sprint 17. Sprint 17 implementation
is in progress and release-blocking from the sealed deep scan of revision
`3e27c82`, which reported 12 findings and four deferred questions. Local
controls, N-1 reconciliation and a ten-stage PostgreSQL browser workflow are
green, and PR 109 protected GitHub gates passed on substantive candidate
`a02fd6d3`. Assigned-QC self-claim and object-aware audience enforcement are
implemented with memory and PostgreSQL regression evidence. The remaining
authorised staging checks remain open. The final local candidate passes 962
backend tests, 414 frontend tests and the ten-stage PostgreSQL browser workflow.
The repository owner deferred the fresh sealed scan on 2026-07-13, so
fresh-scan closure is not claimed. Local
development remains supported; GCP and Kubernetes remain migration targets.

A sealed standard review `87a10d13-14af-48cc-a361-72470abc8d8d` of later
revision `752d32a` validated eight additional application findings and is the
current application baseline. The 2026-07-14 remediation candidate
separates create/publish and edit/transition authority, makes credential and
session revocation monotonic, bounds shared Argon2 work, makes failed logout
fail closed in the browser, and prevents draft links creating audience
authority. The final local gates pass 68 PostgreSQL and 915 non-PostgreSQL
backend tests at 98.13 percent line and 95.01 percent branch coverage, plus 432
frontend tests at 98.51 percent line and 95.01 percent branch coverage.
Dependency audits report no known vulnerabilities. The immutable-candidate
deep scan and authorised staging evidence remain open, so release closure is
not claimed.

An approved local-demo workforce refinement is tracked separately from Sprint
17 security closure. It keeps one generic Analyst role, replaces specialist
analyst seed identities with neutral numbered logons, adds realistic but wholly
synthetic Scottish-footballer-named profiles, preserves team-authoritative
assignment and reconciles existing local seed state without a destructive
reset. Its contract is `docs/specs/generic-analyst-seed-personas.md` and its
architecture decision is ADR 0029. The slice is implemented: 68 PostgreSQL and
919 non-PostgreSQL backend tests pass at 98.13 per cent line and 95.04 per cent
branch coverage; the full frontend suite passes at 98.51 per cent line and
95.01 per cent branch coverage, and live local reconciliation was verified.

A post-Sprint-17 customer-experience slice is now implemented. It replaces
the request metric-card mosaic, removes the backend completeness checklist from
the customer chat, adds a searchable selected-detail ACG journey, moves profile
editing to a read-first account page and provides assigned analysts with lazy
full conversation context. Its contract is
`docs/specs/customer-experience-and-analyst-context.md` and ADR 0030. The full
frontend suite passes with 447 tests at 98.54 percent line and 95.15 percent
branch coverage. The backend passes 922 non-PostgreSQL and 68 PostgreSQL tests
at 98.14 percent line and 95.09 percent branch coverage.

Sprint 19 is implemented and locally verified. It adds 144 deterministic four-page PDF products,
15 specialist ACGs, an explicit 56-of-58 Billy Gilmour access matrix and search
score calibration. Its contract is
`docs/specs/synthetic-intelligence-library-and-search-assurance.md` and ADR 0031.

The admin command-centre refinement is implemented under
`docs/specs/admin-command-centre-and-analytics.md`. It adds compact configuration
disclosures, explicit saved/active/tested states, a bounded Realtime voice
connection test, admin return navigation and an operational analytics view
derived only from the existing authorised aggregates. Full local gate evidence
is green: 507 frontend tests pass at 98.69 per cent line and 95.05 per cent
branch coverage; 1,072 non-PostgreSQL and 70 real-PostgreSQL backend tests pass
at 98.08 per cent line and 95.08 per cent branch coverage.

The customer-search and autonomous-routing orchestration is implemented under
`docs/specs/customer-search-routing-orchestration.md` and ADR 0036. Submission
now starts bounded product discovery, separates offers from definitive no-match
and incomplete outcomes, offers authorised active work before owner-only new
tasking consent, and routes authorised new work through a policy-constrained
JIOC agent. JIOC managers have an audited on-the-loop intervention queue;
customers receive safe stage and ETA projections; collection-to-analysis
handoffs retain versioned context; deterministic QC preflight cannot bypass the
human release authority. The clean PostgreSQL-backed gate passes 1,176 tests
with one intentional compatibility skip at 98.09 per cent line and 95.12 per
cent branch coverage. The frontend passes 518 tests at 98.85 per cent line and
95.05 per cent branch coverage.

The 20 July 2026 agent-safety hardening milestone is in progress. Candidate
implementation and focused regression tests now cover fail-closed JIOC rollout,
bounded model output and provenance, outbox operations, agent authority and
static boundaries. Full local gates and independent code-quality and security
reviews remain open, so completion and `active` routing approval are not claimed.

## Delivery Ledger

| Sprint | Scope                                                                                                                                                                                                                                                                                                     | Status                       | Verification                                                                                                                                                                                                         |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1      | Skeleton, monorepo, API/web shells, Compose and quality gates.                                                                                                                                                                                                                                            | Complete                     | Local backend/frontend/security gates passed on 2026-07-04.                                                                                                                                                          |
| 2      | Auth, sessions, RBAC, role navigation, seed users and branch protection docs.                                                                                                                                                                                                                             | Complete                     | Local auth, CI and browser gates passed on 2026-07-04.                                                                                                                                                               |
| 3      | ACGs, product access diagnostics and product access policy.                                                                                                                                                                                                                                               | Complete                     | Local access-control gates passed on 2026-07-04; legacy workspace surface retired by ADR 0018.                                                                                                                       |
| 4      | Ticket intake, mock chatbot, editable intake, attachments, timeline and customer dashboard.                                                                                                                                                                                                               | Complete                     | Local ticket-intake gates passed on 2026-07-05.                                                                                                                                                                      |
| 5      | Intelligence Store metadata, search, detail, upload and controlled asset access.                                                                                                                                                                                                                          | Complete                     | Local store and access-regression gates passed on 2026-07-05.                                                                                                                                                        |
| 6      | Deterministic synthetic product generation and seed manifests.                                                                                                                                                                                                                                            | Complete                     | Local generator, security and file-line gates passed on 2026-07-05.                                                                                                                                                  |
| 7      | RFI Search Agent, hybrid ranking, product offers and search metrics.                                                                                                                                                                                                                                      | Complete                     | Local RFI search, Semgrep and UI gates passed on 2026-07-05.                                                                                                                                                         |
| 8      | RFA/CM routing agents, manager queues, approvals, clarifications and overrides.                                                                                                                                                                                                                           | Complete                     | Local routing, Semgrep and UI gates passed on 2026-07-05.                                                                                                                                                            |
| 9      | Analyst workbench, assignment, work packages, notes, linked products, drafts and QC submission.                                                                                                                                                                                                           | Complete                     | Local analyst, Semgrep and UI gates passed on 2026-07-05.                                                                                                                                                            |
| 10     | QC queue, checklist, rejection, auto-ingestion, indexing, dissemination and feedback requests.                                                                                                                                                                                                            | Complete                     | Local and GitHub backend, frontend, Semgrep and CodeQL gates passed on 2026-07-05.                                                                                                                                   |
| 11     | Feedback submission, admin/RFA/CM dashboards, product reuse analytics and Trends Analysis Agent.                                                                                                                                                                                                          | Complete                     | Local backend, frontend, Semgrep and security gates passed on 2026-07-05.                                                                                                                                            |
| 12     | Inactive future GCP migration reference: Terraform, Cloud Run, Cloud SQL, Cloud Storage, Secret Manager, Pub/Sub, Artifact Registry and AI provider configuration.                                                                                                                                        | Reference complete, inactive | Reference validation passed on 2026-07-05; no live GCP runtime is supported or required.                                                                                                                             |
| 13     | Security hardening, container scans, SBOM, DAST, Terraform scanning, prompt-injection suite and air-gapped notes.                                                                                                                                                                                         | Complete                     | Local backend, frontend, Semgrep, Checkov and Gitleaks gates passed on 2026-07-05; Docker-backed checks run in GitHub Actions.                                                                                       |
| 14     | Close the original 2026-07-10 security findings and improve SOLID boundaries, maintainability, independent coverage gates and real integration testing.                                                                                                                                                   | Historical, superseded       | Its later release obligation moved through Sprint 14B and is now owned only by Sprint 17.                                                                                                                             |
| 14B    | Remediate the sealed 16-finding baseline and its verification findings.                                                                                                                                                                                                                                    | Superseded by Sprint 17      | The original baseline was closed, but deep scan `abf0e143` of later revision `3e27c82` established the current 12-finding baseline.                                                                                  |
| 15     | JIOC workflow restructure: role renames plus JIOC Team Member, JIOC routing queue, customer collect choice, manager approval chain, QC-owned release with the CM-to-RFA analysed-collect leg, multi-analyst assignment, teams/profiles/availability calendars, and the permission-refresh-on-restore fix. | Implementation delivered     | Backend and web suites passed; the complete eight-role real-browser acceptance evidence is carried into Sprint 17. See ADR 0022 and the workflow specifications.                                                     |
| 16     | Cross-role desktop usability, multi-provider AI administration and documentation/deployment accuracy.                                                                                                                                                                                                     | Complete                     | PRs #98-#100 passed protected GitHub checks; coverage remained above 95%; current guides distinguish the supported local runtime from GCP/Kubernetes migration targets.                                              |
| 17     | Close the current security baseline, introduce secure control ownership, improve SOLID boundaries and reconcile all active documentation without breaking intended behaviour.                                                                                                                            | Implementation in progress   | Earlier local controls, logical restore, N-1 reconciliation, PostgreSQL browser evidence and protected GitHub gates pass. The 2026-07-14 eight-finding remediation candidate passes full local coverage and dependency gates; external staging and a fresh sealed deep scan remain open. |
| 18     | Customer request, conversational intake, searchable ACG, read-first profile and assigned-analyst conversation-context redesign.                                                                                                                                                                          | Implementation complete      | 447 frontend, 922 non-PostgreSQL and 68 PostgreSQL tests pass above the separate 95 percent line and branch gates; browser acceptance is recorded in the delivery handoff.                                             |
| 19     | Deterministic live-demo PDF corpus, specialist ACG matrix and Store/RFI search assurance.                                                                                                                                                                                                                | Implementation complete      | 993 backend tests pass with PostgreSQL at 97.62 percent combined coverage; frontend passes at 98.54 percent line and 95.09 percent branch coverage, with a successful production build and visual PDF inspection.       |
| 20     | Grounded generation-aware Intelligence Store retrieval, independent search embedding administration and full-corpus RFI/RFA duplicate assurance.                                                                                                                                                       | Implementation complete      | 1,129 backend tests pass with real PostgreSQL and pgvector at 98.16 percent line and 95.12 percent branch coverage. Live browser checks prove hybrid cited offers, visible-customer duplicate joining and manager RFA discovery. |
| 21     | Compact admin command centre, explicit provider/key state, Realtime connection assurance, return navigation and separate aggregate-only admin analytics.                                                                                                                                                 | Implementation complete      | 507 frontend, 1,072 non-PostgreSQL and 70 real-PostgreSQL tests pass above the separate 95 per cent line and branch gates; static, contract and live browser acceptance checks pass.                                   |
| 22     | Customer-controlled product resolution, assured no-match, active-work joining, autonomous policy-constrained JIOC routing, manager intervention, safe tracking and deterministic QC preflight.                                                                                                             | Implementation complete      | 1,176 backend tests and one intentional skip pass at 98.09 per cent line and 95.12 per cent branch coverage; 518 frontend tests pass at 98.85 per cent line and 95.05 per cent branch coverage.                          |
| 23     | Agent-safety hardening for JIOC rollout, routing evidence, bounded LLM output, safe run provenance, outbox replay and authority boundaries.                                                                                                                                                                 | Implementation in progress   | Candidate implementation and focused regressions are present; full quality gates, labelled v2 activation evidence and independent reviews remain open.                                                               |

## Sprint 12 Future Reference Scope

- Terraform dev baseline under `infra/gcp/environments/dev`.
- Modular Terraform for GCP services, IAM, Artifact Registry, Cloud Run, Cloud
  SQL, Cloud Storage, Secret Manager and Pub/Sub.
- GitHub OIDC Workload Identity Federation without service account keys.
- Manual migration-reference workflow for Terraform validation and local image
  builds only; no active cloud deployment path.
- Production web container image for Cloud Run.
- Runtime settings for GCP, GCS, Pub/Sub and supported AI provider configuration.
- Sprint 12 spec, ADR, threat model and GCP dev deployment runbook.

This material is not a supported current deployment target. Coeus remains a
local, single-instance application until the readiness gates in ADR 0019 pass.

## Sprint 14 Delivered Scope

- Closed 16 original exploit paths and contained the unsupported multi-replica
  session primitive behind local, runtime, IaC and migration-readiness gates.
- Centralised actor-scoped linked-product response policy and bounded analyst
  task, linked-product, similarity and Store projection work.
- Added append-only audit stores, per-username compare-and-restore lockout
  state, atomic registration capacity and decisions, and exact-byte QC assets.
- Split application composition, introduced narrow access, Store and object
  storage protocols, decomposed analyst UI orchestration, and consolidated the
  frontend request transport.
- Replaced the dormant cloud deploy workflow with validation and local image
  builds only, plus a default-deny Terraform migration gate.
- Added separate backend line and branch gates and a real local-stack browser
  flow.

## Sprint 14 Verification Before Security Seal

- Backend Ruff, mypy and pytest: 490 passed, 98.28 percent line coverage and
  95.05 percent branch coverage.
- Frontend Prettier, ESLint, TypeScript and Vitest: 322 passed, 98.77 percent
  line coverage and 95.54 percent branch coverage.
- Frontend Knip, production build, pnpm production audit and the 350-line gate:
  passed.
- Playwright Chromium: 3 passed, including a real Vite-to-FastAPI login and
  request-creation flow without API interception.
- Bandit, pip-audit, Semgrep tracked and untracked scans, Gitleaks changed
  content, Actionlint and Checkov: passed with no reportable finding.
- Terraform 1.10.5: format and validate passed; migration gate 1 of 1 and
  single-writer module tests 3 of 3 passed.
- API container rebuilt; Trivy found zero high or critical vulnerabilities
  when ignoring unfixed issues.

## Sprint 14B Remediation Ledger

The sealed scan of revision `72a0dc58` supersedes the pre-seal completion
claim. Its reportable baseline is:

- P2: exposed local-network PostgreSQL superuser, blocking Store embeddings
  and unbounded chat history.
- P3: blocking RFI embeddings, buffered asset downloads, corpus-linear Store
  embeddings, hybrid and RFI matcher stalls, readiness connection fan-out,
  unbounded product assets, attachment metadata and analyst drafts,
  unpaginated ticket and routing collections, audit pagination loss and a
  false-green ZAP gate.

Revision `7165e49e` integrated the feature slice, passed the full local gates
and closed all 16 baseline findings. The sealed verification scan
`a089e83c-afc7-4213-8763-4a5e5759598d` then found three Low/P3 issues:

- chat and intake saves were not failure-atomic with central audit append;
- an offloaded RFI worker could overwrite a newer authorised ticket update.

The current fix uses a repository-locked save-plus-confirmation boundary,
optimistic ticket snapshot compare-and-swap, conditional rollback, cursor-based
compact request summaries and an explicit browser-dictation privacy notice.
This is historical Sprint 14B evidence. Deep scan `abf0e143` of later revision
`3e27c82` supersedes its release-closure state and defines Sprint 17.

## Sprint 15 Workflow Integrity And Area Oversight

Status: implementation delivered; full-role browser acceptance evidence is
carried into Sprint 17.

- Make the selected organisational team authoritative for assignment,
  availability and membership while allowing RFA and CM managers to operate
  across every team in their respective area.
- Add bounded, read-only JIOC oversight across queues, teams, analysts and task
  load without exposing product bodies, analyst notes or draft content.
- Add self-service ACG applications for every user and delegated, audited
  approval by up to eight cross-role administrators per ACG.
- Correct clarification resumption, rework version gates, analyst task access,
  credential-reset atomicity and release audit compensation.
- Finish ACG identity administration, mutation recovery, calendar accuracy,
  branded route recovery and role-specific loading and error states.
- Repair the local Alembic/reset/Compose workflows and make Node, GCP and
  Kubernetes guidance match the actual supported boundaries.

The acceptance criteria are in
`docs/specs/workflow-integrity-area-oversight-remediation.md` and ADR 0023. The
delivery and role-walkthrough evidence is recorded in
`docs/DEVELOPMENT_STORY.md`.

## 18 July 2026 External Product Lifecycle Milestone

Status: implemented and verified locally.

- Assigned analysts can upload immutable DOCX, PPTX, PDF, PNG, JPEG and WebP
  products with title, summary, description, product/source type, owner, area,
  dates, tags, classification, releasability, caveats and one or more ACGs.
- File signatures and Office structure are checked server-side. Spoofed types,
  macros, external Office relationships, malformed files, empty files, EICAR
  test content and over-limit uploads fail closed.
- Manager approval pins the exact submission manifest. Human QC sees a safe
  preview or extracted-text fallback beside deterministic UK-English proofing
  findings, then releases the same source bytes into the Intelligence Store.
- Released products use existing Store ACG controls, protected inline preview
  and exact-byte download. Customer acceptance closes the requirement;
  rejection returns to the responsible RFA or CM manager, with disagreement
  adjudicated by an independent JIOC human.
- Raster images without trusted OCR produce an explicit proofing-coverage
  warning. Production Office rendition and OCR remain separate worker
  capabilities, and hosted upload remains unavailable until a malware scanner
  is configured.

Verification evidence:

- Backend: 1,206 passed, one intentional N-1 compatibility skip, 97.12 per cent
  combined coverage with disposable PostgreSQL migration, transaction,
  concurrency, codec and projection tests enabled.
- Frontend: complete Vitest suite passed at 98.29 per cent lines/statements,
  95.04 per cent functions and 95.00 per cent branches.
- Ruff, backend formatting, mypy, ESLint, Prettier, TypeScript, OpenAPI
  generation, architecture, security-policy, documentation and 350-line gates
  passed.

## 18 July 2026 Quality, SOLID And Security Remediation

Status: implemented and verified for the supported local-first deployment
boundary.

- Closed the password-change current-state race and bounded durable sessions
  with atomic confirmation, expiry pruning, per-user and global admission, and
  rollback-safe session issue.
- Replaced coarse draft-preview permissions with one live object policy over
  the exact ticket, version and asset. Clearance, active ACG membership,
  workflow state and current analyst, same-route manager or named-QC ownership
  are checked before any storage read. Administrators have no implicit content
  authority.
- Added receive-time upload limits, permission-before-parse ordering, bounded
  Office archive reads, hardened PPTX XML, Windows-safe restore paths and a
  capacity-neutral registration response.
- Removed confirmed dead code, including the superseded similar-request join
  implementation, and added production Knip plus Python declaration analysis.
- Moved API composition out of services, narrowed repository and provider
  ports, enabled C901, centralised frontend route policy and query identity,
  and split request and routing mutation hotspots.
- Corrected protected Blob lifetime, forced-reset contract use, dirty-draft
  refresh, 409 reconciliation, 413 recovery and reported accessibility states.

Verification evidence:

- Backend: 1,233 passed, one intentional external N-1 source-tree skip, 98.13
  per cent line coverage and 95.15 per cent branch coverage, including the
  supported PostgreSQL integration stack.
- Frontend: 530 passed at 98.65 per cent line, 95.05 per cent function and
  95.14 per cent branch coverage.
- Formatting, Ruff, strict mypy, ESLint, TypeScript, architecture, C901,
  350-line, OpenAPI compatibility, documentation, security-policy and both
  dead-code modes pass. Dependency audits, Bandit and scoped redacted Gitleaks
  working-tree scans are clean.
- The closure ledger is
  `docs/security/SECURITY_REVIEW_REMEDIATION_2026-07-18.md`; ADRs 0038 and 0039
  record the identity and protected-draft boundaries.

## 20 July 2026 Agent-Safety Hardening

Status: complete. Independent code-quality and security reviews were remediated;
the final candidate passed 1,333 backend tests with one intentional skip and
530 frontend tests, with both line and branch coverage above 95 per cent.

### Candidate Checklist

- [x] Prove `disabled` invokes no capability agent and only refers to human
  review, while `shadow` records
  comparison evidence without route side effects, and only an explicitly
  allowlisted `active` release may apply deterministic transitions.
- [x] Prove routing fails closed to clarification or human review for
  conflicting or negated signals, stale or missing context, restrictions,
  unavailable or missing candidate-team capacity and unmet evaluation evidence.
- [x] Approve the versioned `jioc-routing-policy-v2` labelled activation gate;
  `active` remains blocked until conflict, negation, stale-context, capacity and
  authority cases pass and the release identifier is allowlisted.
- [x] Prove the model-backed action selector has token, identity-encoding, byte
  and timeout bounds, a closed output vocabulary and deterministic fallback,
  while `AgentRun` retains
  safe provider/model/version/timing/outcome provenance without secrets, raw
  prompts or unnecessary customer content.
- [x] Prove bounded outbox health and dispatch metrics plus authorised,
  reason-required, audited replay that keeps the original event identity and is
  idempotent for pending, delivered and dead-lettered events.
- [x] Confirm the agent authority matrix and static dependency gates prevent
  deterministic routing or QC modules from importing provider adapters and
  prevent outbound adapters from gaining workflow or persistence authority.

### Verification Gates

- [x] Full backend suite passes with real PostgreSQL and at least 95 per cent
  line and branch coverage.
- [x] Full frontend suite, production build and separate 95 per cent line and
  branch gates pass.
- [x] Formatting, Ruff, mypy, ESLint, TypeScript, architecture, line-limit,
  OpenAPI, documentation, dependency and security gates pass.
- [x] Independent code-quality and cyber-security reviews complete, with all
  accepted findings fixed or explicitly recorded as blockers or risks.

### Deferred Gates, Risks And Next Step

- Before real or sensitive data, require approved classification,
  DLP/redaction and egress policy; provider/model/region allowlists; retention;
  a representative human-labelled corpus; calibration, drift and rollback
  evidence; and a decision on any richer provider context.
- LiteLLM adoption remains deferred. Reconsider it only when an approved
  multi-provider gateway need justifies the added secret, egress, logging and
  failure boundary, with an ADR and threat-model update before adoption.
- Current residual risk: operational availability remains a process-local
  snapshot in the supported single-worker runtime. A shared authoritative
  adapter and scale-out evaluation are required before multi-replica routing.
- Current next step: keep production routing `disabled`, gather labelled shadow
  evidence, satisfy the real-data governance gates, then run a reviewed canary.
