# Coeus Development Story

Sprint 1 to Sprint 13 entries live in
[DEVELOPMENT_STORY_SPRINTS_01-13.md](DEVELOPMENT_STORY_SPRINTS_01-13.md).

## 2026-07-09 Access-control audit rollback

- Hardened ACG administration so create, update, membership-add and
  membership-remove operations restore the previous repository state if audit
  recording fails. Added regression coverage for all four mutation paths and
  updated the ACG project-access threat model.
- Hardened notification and email side effects so notification creation,
  mark-read and email outbox writes restore previous state if persistence or
  audit recording fails. Added regression coverage and updated the manager
  final-release threat model.
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

## 2026-07-06 Frontend design and role-view polish

- Reworked the frontend design system for a dark, operational look: expanded
  colour tokens with graphite surfaces and cyan, teal, green, amber and red
  accents, a monospace accent face for references and tokens, grouped
  navigation with section labels, a sticky blurred command bar with a
  Ctrl+K shortcut, subtle hover and focus motion, and a technical grid
  backdrop on the auth pages. All animation respects
  `prefers-reduced-motion` and the light theme remains supported.
- Completed the manager-to-analyst workflow in the UI: after route approval a
  ticket now stays in the routing queue with an assign-analyst panel backed by
  the existing `/analyst/candidates` and `/analyst/tasks/{id}/assign`
  endpoints, so tickets no longer dead-end in `ANALYST_ASSIGNMENT`.
- Gated ACG create, update and add-member forms behind `acg:create`,
  `acg:update` and `acg:assign_user` permissions so view-only roles no longer
  see actions they cannot use.
- Added shared `LoadingState`, `ErrorState`, `EmptyState` and `StatusPill`
  components with styles for the previously unstyled `request-row` and
  `status-pill` classes, and wired loading, error, empty and success states
  into the store, analytics, audit, requests, routing, analyst, QC
  and ACG pages.
- Preserved product back-navigation context from team workspaces, and relabelled
  the controlled asset grant with token expiry.
- Verified all eight role views end to end in the browser, including the full
  intake, RFI search, routing, assignment, analyst production and QC
  dissemination pipeline, auth negative states and responsive layouts at
  1440x900, 1280x720, 768x1024 and 390x844.

## 2026-07-06 Istari rebrand, splash login and access requests

- Rebranded the product from Coeus to Istari across the web UI, page
  metadata, favicon and the FastAPI docs title, using the supplied logo with
  resized 64px and 256px assets. Internal package, module and infrastructure
  identifiers keep the `coeus` working name.
- Rebuilt the login page as a splash introduction: glowing, gently floating
  logo, "Task. Assess. Deliver." tagline, a short pitch, three capability
  points and an access card that switches between sign in and request
  access. Animations remain CSS-only and respect `prefers-reduced-motion`.
- Added a self-service registration flow: public `POST /auth/register` with
  Argon2 hashing at submission, generic anti-enumeration responses, a
  pending-request cap with `429` throttling, and admin review endpoints
  gated by `user:create` plus CSRF. Approval creates an active `User`
  account at clearance level 1; decisions are audit logged.
- Added an Access Requests panel to the admin overview for approving or
  rejecting requests with a recorded reason, plus a spec and threat model
  for the feature.
- Verified in the browser: request submission, admin approval, first login
  of the approved account, rejection with generic sign-in failure, splash
  responsiveness at 390, 768 and 1440 widths and the light theme.

## 2026-07-06 Splash hero, focused customer workspace and collaboration

- Enlarged and centred the Istari splash hero for desktop with a slow
  radar-sweep ring around the badge, a pulsing glow, a gently floating logo
  and a gradient title, all CSS-only and reduced-motion safe.
- Simplified the customer experience into two focused screens: a request
  dashboard (status metrics, request list with tagged counts and one "Open
  new request" action) and a chat-first request workspace at
  `/app/requests/:id`. The workspace shows a live checklist of the seven
  details the intake assistant needs, keeps the manual intake form and
  request history behind progressive-disclosure sections, and only shows
  product offers once a request has been submitted.
- Added ticket collaborators: requesters tag users from a directory as
  editors or viewers. Tagged users see shared requests on their dashboard
  and via direct link from any role; editors can chat and edit within their
  own permissions while viewers get a read-only conversation. Added a
  `colleague@example.test` seed user, timeline and audit events, a spec and
  a threat model.
- Added administrator AI model selection backed by
  `GET/PUT /api/v1/admin/ai-model` with an audited, CSRF-protected switch
  between configured Gemini models, and fixed the CORS method list to allow
  PUT.
- Extended the Intelligence Store with coverage date search
  (`dateFrom`/`dateTo` period-overlap filtering, seeded synthetic coverage
  periods), product-format icons for geospatial, imagery, SIGINT, database,
  bundle and report types, and coverage/classification chips on results and
  detail pages.
- Verified in the browser: dashboard to chat intake with live checklist,
  tagging and shared editing as the colleague user, date-filtered store
  search, the admin model switch persisting to the backend, audit events
  and responsive layouts at 390 and 1440 widths.

## 2026-07-06 Manager final release, notifications and store polish

- Restricted intelligence product uploads to RFA and Collection managers by
  moving `product:create_existing` out of the shared product-team
  permission set; the store upload route and button follow automatically.
- Added a manager final-release stage: QC approval now ingests and indexes
  the product as an unpublished draft and moves the ticket to the new
  `MANAGER_RELEASE` state. The owning RFA or Collection manager releases
  it from a Final Release panel on their queue page, which publishes the product,
  disseminates it to the requester, raises the feedback request and moves
  the ticket to `DISSEMINATION_READY`. Route matching, CSRF, separation of
  duties and audit events are enforced, with a spec and threat model.
- Added customer notifications: releases create an in-app notification
  with a product link and record an email to a bounded local outbox with
  an `email_recorded` audit event. The shell bell shows an unread badge,
  lists notifications, marks them read and navigates to the product; the
  customer dashboard links released products directly.
- Made the Intelligence Store feel like a professional service: a
  collapsible search-and-filters panel, a sort control (relevance, title,
  newest coverage), mono product references, format icons and richer
  metadata everywhere, including tags, releasability, caveats, source,
  status and per-asset mime type, size and hash digests.
- Fixed the CORS allow list to include PUT, which the admin AI model
  switch needed.
- Verified in the browser: the full pipeline from chat intake through QC
  approval and manager release, the customer receiving the bell
  notification and released-product link, upload visibility per role and
  the audit trail recording qc_approved, product_released and
  email_recorded.

## 2026-07-06 Themed ACGs, request journey and agentic UX

- Seeded 43 access control groups: the three workflow groups plus a
  40-group themed catalogue built from eight regions crossed with five
  intelligence disciplines (European Cyber, African HUMINT, Maritime
  GEOINT and so on), with realistic role memberships so store need-to-know
  filtering demonstrates overlap. No access-control logic changed.
- Added a transient "Request journey" dialog for requesters that maps
  every workflow state onto seven plain-language stages with a "you are
  here" marker. It opens automatically once on ticket submission, on
  demand from the workspace meta bar, and closes on Escape, overlay click
  or the close button.
- Pushed the role screens further towards an AI-first feel: the chat is
  now the customer chatbot with a typing indicator, machine-generated
  recommendation cards carry agent chips (orchestrator, capability agent,
  RFI search agent), the analyst detail collapses notes and linked products
  behind disclosures, and manager queues collapse the clarification and
  rejection forms behind "Query or reject this route".
- Rebuilt the admin AI model chooser as a card catalogue with tier chips
  (Sovereign, Fast, Advanced, Custom fallback) and per-model descriptions,
  an Active badge, and a last-changed line backed by new
  `changedBy`/`changedAt` fields on the admin AI model endpoint.
- Verified in the browser end to end: customer intake to submission with
  the journey auto-opening, RFI offer rejection, RFA manager capability
  checks and approval with agent chips, analyst workbench disclosures,
  the admin model switch recording the change, and the themed ACG list.
- Checks: line limit, Prettier, ESLint, tsc, Vitest coverage (99.8% lines,
  95.9% branches), pytest coverage (95.61%, 139 tests), mypy and ruff all
  pass.

## 2026-07-06 Quality, security and documentation pass

- Ran code-quality and defensive-security reviews and acted on the findings.
- Fixed real frontend bugs: the analyst workbench now remounts per task so an
  unsent note or draft cannot carry across to a different task; the store "My
  Products" scope maps owner team to role by an explicit matcher (RFA managers
  previously saw an empty list); the routing queue clears its selection when a
  ticket is routed away instead of silently showing an unrelated one; the request
  journey handles cancelled requests; and the admin rejection reason clears after
  use. Each fix has a regression test.
- Hardened the backend, secure by design: start-up now fails closed if dev seed
  users are enabled without overriding the default seed credential (closing a
  public-deploy admin-access risk); the API sets a narrow CSP always and HSTS
  over TLS, and the nginx SPA config sets a full CSP plus HSTS; asset object keys
  are reduced to a safe path segment; and asset size has an upper bound at the
  schema boundary.
- Overhauled the documentation: a rewritten README, a docs index, and new Setup,
  User, Roles and User Stories, and AI Agents guides, with twelve annotated
  screenshots of every role workspace (all synthetic, MOCK DATA ONLY). Recorded
  the security changes and remaining deferred risks in the threat model.
- Checks: line limit, Prettier, ESLint, tsc, Vitest coverage (99.8% lines,
  95.9% branches), pytest (145 tests, 95.62%), mypy and ruff all pass.

## 2026-07-06 Ambient UI effects

- Adapted React Bits-style ParticleField, SpotlightCard and CountUp effects as
  dependency-free, reduced-motion-safe components.
- Added CSS-only shine, stagger, pulse and notification badge effects, refreshed
  splash screenshots, and passed the frontend gates: 213 tests, 99.75% lines,
  95.95% branches, ESLint, tsc, Prettier and the line limit.

## 2026-07-06 Request controls and user administration

- Requesters can cancel cancellable requests with a recorded reason, clarification
  requests surface in chat, and request mutation failures alert.
- Added `/admin/users` for role assignment, clearance and activation changes,
  protected by `user:assign_role` and guarded against editing the signed-in
  account.
- Browser verification covered admin overview, the Users screen with 10 seeded
  accounts, and creating then cancelling a request.
- Checks: Prettier, ESLint, TypeScript, line limit, Ruff, Knip, targeted Vitest
  coverage, full Vitest coverage (219 tests, 99.71% lines, 95.69% branches) and
  pytest (151 tests, 95.54%) all pass.

## 2026-07-06 No-GCP hardening and local-first docs

- Added local/test admin reset, store pagination, owner-team filters, a mocked
  Playwright workflow, tighter intake extraction and local-first GCP docs.

## 2026-07-06 Local persistence, files and integrations

- Added PostgreSQL-backed local persistence, real Store asset bytes, signed
  downloads, admin-managed Gemini settings and optional SMTP.
- Mirrored Store products into relational PostgreSQL tables, refreshed Store
  reads from them, and added SQL-side access predicates for search, detail and
  asset grants with API policy rechecks.

## 2026-07-06 Agent clarification handoff

- Added explicit orchestrator/customer-chatbot clarification handoff: capability and manager questions now become requester-visible assistant messages, agent runs and a `customer_clarification_sent` event.
- Added a restricted-read admin break-glass form on denied Store product pages; the UI requires a reason and uses the audited support endpoint.
- Exposed the synthetic RFA/CM capability catalogue through a manager-only routing endpoint and queue-side panel.

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
- Removed the remaining runtime shims for retired workspace state. Older local
  snapshots that contain those fields should be reset before use.
- Added ADR 0018 and refreshed the ACG/product access threat model and Sprint 3
  spec to record the retirement decision.
