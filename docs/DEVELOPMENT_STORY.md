# Coeus Development Story

Sprint 1 to Sprint 13 entries live in [DEVELOPMENT_STORY_SPRINTS_01-13.md](DEVELOPMENT_STORY_SPRINTS_01-13.md). The longer 2026-07-06 continuation lives in [DEVELOPMENT_STORY_2026-07-06.md](DEVELOPMENT_STORY_2026-07-06.md).

## 2026-07-09 Access-control audit rollback

- Hardened ACG administration so create, update and membership changes restore
  previous repository state if audit recording fails. Added regression coverage
  and updated the ACG product-access threat model.
- Hardened notification and email side effects so creation, mark-read and
  email outbox writes restore previous state if persistence or audit recording
  fails. Updated the manager final-release threat model.
- Hardened admin AI model configuration so failed model selection or Gemini API
  key configuration restores the previous provider, model, key and change
  metadata. Added persistence and audit-failure regression coverage.
- Hardened RFA and CM routing so route reviews, approvals, rejections and
  clarification requests restore the original ticket if audit recording fails
  after the ticket update. Added rollback regression coverage for each path.
- Hardened QC approval and rejection so audit recording failure restores the
  original ticket state. Approval also discards the ingested Store product and
  local placeholder asset bytes so a failed request does not leave an orphaned
  draft product.
- Hardened final product release so `product_released` audit failure restores
  the ticket to `MANAGER_RELEASE`, returns the Store product to draft status
  and suppresses requester notification.
- Hardened similar-request customer join and manager link actions so audit
  recording failure restores the affected ticket records instead of leaving
  unaudited collaborator grants or related-ticket links.
- Hardened direct ticket collaborator add and remove actions so audit
  recording failure restores the original ticket, preventing unaudited access
  changes.
- Hardened requester lifecycle actions so cancellation, no-match consent and
  delivery confirmation restore the original ticket if audit recording fails
  after the proposed state update.
- Hardened RFI search run, offer acceptance and offer rejection so audit
  recording failure restores the original ticket, preventing unaudited search
  outcomes or product decisions.
- Hardened analyst assignment, notes, product links, work-package updates,
  draft saves and QC submission so failed audit recording restores the original
  ticket state.
- Hardened Store product ingestion so `product_created` audit failure restores
  product metadata and uploaded bytes, and storage failure does not leave a
  false product-created audit event.
- Hardened auth session lifecycle changes so failed `login_success`, `logout`
  or `password_changed` audit restores sessions, credentials and login attempts.
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
