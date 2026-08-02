# Coeus Development Story: Early July 2026 Milestones

These historical entries were moved from the active development story to keep
the current record within the repository line limit.

## 2026-07-27 workflow review remediation

- A four-angle workflow review confirmed and fixed eight defect groups
  (capacity leak, `INFO_REQUIRED` regression, uploaded-rework QC deadlock,
  deactivated-account strands, untested chunk-index access predicates,
  requester-lockout error surfacing, unchanged re-analysis re-release, and
  smaller timezone, slicing, invariant and state-map issues) under the
  [remediation contract](specs/workflow-review-remediation-2026-07-27.md),
  with the terminal set now derived from the state machine and migration
  `20260727_0015` backfilling projected rows. Documented the Realtime Voice
  Intake channel and the shipped workflow operational guarantees.

## 2026-07-23 JIOC operating model and Manager journey

- Fixed Agent clarification hand-offs and tested distinct Team Member and Manager authority.
- Added Agent evidence, attention-first oversight, deep links and six JIOC diagrams.
- Reconciled guides, specifications and threat models with shared human review plus Manager-only oversight and intervention.

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

## 2026-07-08 Architecture documentation

- Added the initial grounded architecture guide split by responsibility across
  three cross-linked documents with system, workflow and deployment diagrams:
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
