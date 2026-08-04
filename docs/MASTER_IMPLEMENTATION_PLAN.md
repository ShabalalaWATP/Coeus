# Istari (Coeus) Master Implementation Plan

The [root blueprint](../coeus_spec_driven_implementation_plan.md) preserves the
original target state. This file is the current delivery, risk and release tracker.

## Current Stage

As of 3 August 2026, Sprints 1 to 23 are implemented for the supported synthetic
local/test boundary. The 22 July security remediation passed 1,606 backend
tests (one intentional skip) at 98.23/95.33 line/branch and 537 frontend tests
at 98.63/95.03, integrated at `0cde7010` with all protected and post-merge
workflows passing; see its [contract](specs/security-scan-remediation-2026-07-22.md),
[ADR](adr/0042-enforce-security-policy-at-final-boundaries.md) and
[threat model](threat-model/security-scan-remediation-2026-07-22.md).

Finding closure still requires a fresh sealed whole-repository deep scan of the
exact immutable candidate with no unresolved baseline occurrence or new
reportable finding, and production-release closure requires authorised staging
verification. Local development remains the supported runtime; hosted,
multi-instance, GCP, Kubernetes and production operation remain gated targets.

Completed post-Sprint-17 product slices, with point-in-time verification in
the delivery ledger and [development story](DEVELOPMENT_STORY.md):

- generic Analyst seed personas ([contract](specs/generic-analyst-seed-personas.md), [ADR 0029](adr/0029-generic-analyst-role-and-profile-specialisation.md));
- clearer customer, ACG and analyst context ([contract](specs/customer-experience-and-analyst-context.md), [ADR 0030](adr/0030-bounded-self-service-and-analyst-context.md));
- 144 demo PDFs and calibrated search assurance ([contract](specs/synthetic-intelligence-library-and-search-assurance.md), [ADR 0031](adr/0031-deterministic-live-demo-pdf-corpus.md)); and
- the admin command centre and aggregate-only analytics ([contract](specs/admin-command-centre-and-analytics.md), [ADR 0035](adr/0035-separate-admin-platform-analytics.md)).

The latest implemented slices add bounded current-answer intake, automatic
local search-library preparation, richer synthetic report assets, an
asset-first Store detail view, user-owned saved-product folders, and explicit
customer recovery after rejecting all search results. See the
[recovery contract](specs/customer-search-recovery-and-outcomes.md),
[ADR 0046](adr/0046-automatic-local-retrieval-rebuilds.md) and
[ADR 0047](adr/0047-user-owned-intelligence-store-library.md). The Store also
has access-rechecked collaborative projects and private reusable search
subscriptions under the [feature contract](specs/intelligence-store-projects-and-subscriptions.md)
and [ADR 0048](adr/0048-intelligence-store-projects-and-subscriptions.md).

Sprint 24 is approved for phased implementation. Phases 1 to 9 and the local
Phase 11 implementation are now present through Alembic revision
`20260804_0045`. This includes the administrator command surface, canonical
workforce calendars, package planning and handover, conserved capacity,
integrated team workspaces, the 53-person synthetic cohort, the unapproved
relational routing evaluation, exact-candidate cutover records and recovery
evidence. Operational authority cutover is not approved and the default mode
remains non-active. The delivered baseline corrects flat
team capacity and assignment authority, and an explicit PostgreSQL `shadow`
mode now maintains a checkpointed relational organisation projection without
using it for access, routing or workflow decisions. It
will replace flat organisational teams and inaccurate headcount-based
availability with explicit hierarchical organisation units, action-specific
descendant management, canonical personal and team calendars, workflow-derived
team Kanban boards, transactional capacity reservations and a realistic
53-person synthetic workforce. The audited feature contract records the
current limitations, full phased plan and acceptance matrix. See the
[Sprint 24 contract](specs/hierarchical-teams-workforce-calendars-and-task-boards.md),
[ADR 0049](adr/0049-hierarchical-organisations-and-canonical-workforce-capacity.md)
and [threat model](threat-model/hierarchical-teams-workforce-calendars-and-task-boards.md).

Phase 8 now includes a transactionally maintained, password-free
relational account projection. Team-capacity reads use that projection for
active Analyst eligibility inside the same repeatable-read snapshot as
memberships, calendars and reservations. All 40 stable catalogue team IDs now
map explicitly to the synthetic delivery leaves, and the internal JIOC
principal has a revocable `recommendation:view` grant only. The relational
forecast adapter can be composed only for `management` plus routing `shadow`
mode and fails closed on missing authority or evidence. The 48-case routing
gate, including paired deterministic replay, passes. Independent approval and
the remaining cutover evidence are still required, so active mode remains on
the established evaluated context.

The last recorded whole-suite bounded baseline, before revisions 0037 to 0045,
passed 2,410 backend tests with one intentional compatibility skip at 98.16 per
cent line and 95.04 per cent branch coverage. Focused fail-closed suites cover
organisation lifecycle and
restructure persistence, projection drift, workforce calendars, work-package
planning, capacity forecasts, personal-work accountability, contributor
lifecycle, account-aware grant lineage, suspended-account exclusion, package
handover, cutover readiness and team-board row integrity. That baseline's full
frontend suite passed at 98.77 per cent line and 95.04 per cent branch
coverage. Ten established secure-workflow and eight Sprint 24 real-PostgreSQL
browser journeys also passed. Revisions 0037 to 0045 add focused unit,
PostgreSQL, browser, backup and migration evidence, but a fresh whole-suite
protected run of the exact release candidate is still required. Independent
routing approval, independent security review, protected CI and the deployment
cutover decision keep active routing on the established evaluated context.

The customer-search and autonomous-routing orchestration is implemented under
its [contract](specs/customer-search-routing-orchestration.md) and
[ADR 0036](adr/0036-customer-search-assurance-and-agent-routing.md). Submission
starts bounded product discovery, separates offers from definitive no-match and
incomplete outcomes, offers authorised active work before owner-only consent,
and routes new work through a policy-constrained JIOC agent. JIOC managers have
an audited on-the-loop intervention queue; customers receive safe stage and ETA
projections; collection-to-analysis handoffs retain versioned context;
deterministic QC preflight cannot bypass the human release authority. Its
point-in-time gate passed 1,176 backend tests (one intentional skip) at
98.09/95.12 line/branch and 518 frontend tests at 98.85/95.05.

The 20 July 2026 agent-safety hardening milestone is complete. The evaluated v2 JIOC release is active by default for supported synthetic local/test use and autonomously decides CM versus RFA. Hosted mode and approval remain explicit; unsafe cases fail closed to human review. The release approval is independently pinned. Model, provenance, authority and outbox safety passed the local gates.

The 21 July 2026 repair aligns Store metadata and object seeding for non-demo and hosted starts; the ten-stage PostgreSQL journey proves active JIOC routing without a routine manager approval gate and the manager's separate oversight controls.

## Delivery Ledger

| Sprint | Scope                                                                                                                                                                                                                                                                                                     | Status                                      | Verification                                                                                                                                                                                                                                                                                             |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1      | Skeleton, monorepo, API/web shells, Compose and quality gates.                                                                                                                                                                                                                                            | Complete                                    | Local backend/frontend/security gates passed on 2026-07-04.                                                                                                                                                                                                                                              |
| 2      | Auth, sessions, RBAC, role navigation, seed users and branch protection docs.                                                                                                                                                                                                                             | Complete                                    | Local auth, CI and browser gates passed on 2026-07-04.                                                                                                                                                                                                                                                   |
| 3      | ACGs, product access diagnostics and product access policy.                                                                                                                                                                                                                                               | Complete                                    | Local access-control gates passed on 2026-07-04; legacy workspace surface retired by ADR 0018.                                                                                                                                                                                                           |
| 4      | Ticket intake, mock chatbot, editable intake, attachments, timeline and customer dashboard.                                                                                                                                                                                                               | Complete                                    | Local ticket-intake gates passed on 2026-07-05.                                                                                                                                                                                                                                                          |
| 5      | Intelligence Store metadata, search, detail, upload and controlled asset access.                                                                                                                                                                                                                          | Complete                                    | Local store and access-regression gates passed on 2026-07-05.                                                                                                                                                                                                                                            |
| 6      | Deterministic synthetic product generation and seed manifests.                                                                                                                                                                                                                                            | Complete                                    | Local generator, security and file-line gates passed on 2026-07-05.                                                                                                                                                                                                                                      |
| 7      | RFI Search Agent, hybrid ranking, product offers and search metrics.                                                                                                                                                                                                                                      | Complete                                    | Local RFI search, Semgrep and UI gates passed on 2026-07-05.                                                                                                                                                                                                                                             |
| 8      | RFA/CM routing agents, manager queues, approvals, clarifications and overrides.                                                                                                                                                                                                                           | Complete                                    | Local routing, Semgrep and UI gates passed on 2026-07-05.                                                                                                                                                                                                                                                |
| 9      | Analyst workbench, assignment, work packages, notes, linked products, drafts and QC submission.                                                                                                                                                                                                           | Complete                                    | Local analyst, Semgrep and UI gates passed on 2026-07-05.                                                                                                                                                                                                                                                |
| 10     | QC queue, checklist, rejection, auto-ingestion, indexing, dissemination and feedback requests.                                                                                                                                                                                                            | Complete                                    | Local and GitHub backend, frontend, Semgrep and CodeQL gates passed on 2026-07-05.                                                                                                                                                                                                                       |
| 11     | Feedback submission, admin/RFA/CM dashboards, product reuse analytics and Trends Analysis Agent.                                                                                                                                                                                                          | Complete                                    | Local backend, frontend, Semgrep and security gates passed on 2026-07-05.                                                                                                                                                                                                                                |
| 12     | Inactive future GCP migration reference: Terraform, Cloud Run, Cloud SQL, Cloud Storage, Secret Manager, Pub/Sub, Artifact Registry and AI provider configuration.                                                                                                                                        | Reference complete, inactive                | Reference validation passed on 2026-07-05; no live GCP runtime is supported or required.                                                                                                                                                                                                                 |
| 13     | Security hardening, container scans, SBOM, DAST, Terraform scanning, prompt-injection suite and air-gapped notes.                                                                                                                                                                                         | Complete                                    | Local backend, frontend, Semgrep, Checkov and Gitleaks gates passed on 2026-07-05; Docker-backed checks run in GitHub Actions.                                                                                                                                                                           |
| 14     | Close the original 2026-07-10 security findings and improve SOLID boundaries, maintainability, independent coverage gates and real integration testing.                                                                                                                                                   | Historical, superseded                      | Its later release obligation moved through Sprint 14B and is now owned only by Sprint 17.                                                                                                                                                                                                                |
| 14B    | Remediate the sealed 16-finding baseline and its verification findings.                                                                                                                                                                                                                                   | Superseded by Sprint 17                     | The original baseline was closed, but deep scan `abf0e143` of later revision `3e27c82` established the then-current 12-finding baseline.                                                                                                                                                                 |
| 15     | JIOC workflow restructure: role renames plus JIOC Team Member, JIOC routing queue, customer collect choice, manager approval chain, QC-owned release with the CM-to-RFA analysed-collect leg, multi-analyst assignment, teams/profiles/availability calendars, and the permission-refresh-on-restore fix. | Implementation delivered                    | Backend and web suites passed; the complete eight-role real-browser acceptance evidence is carried into Sprint 17. See ADR 0022 and the workflow specifications.                                                                                                                                         |
| 16     | Cross-role desktop usability, multi-provider AI administration and documentation/deployment accuracy.                                                                                                                                                                                                     | Complete                                    | PRs #98-#100 passed protected GitHub checks; coverage remained above 95%; current guides distinguish the supported local runtime from GCP/Kubernetes migration targets.                                                                                                                                  |
| 17     | Close the current security baseline, introduce secure control ownership, improve SOLID boundaries and reconcile all active documentation without breaking intended behaviour.                                                                                                                             | Implementation complete; release gates open | Local controls, logical restore, N-1 reconciliation, PostgreSQL browser evidence and protected GitHub gates pass. Authorised external staging and a fresh sealed deep scan remain open, so production release closure is not claimed.                                                                    |
| 18     | Customer request, conversational intake, searchable ACG, read-first profile and assigned-analyst conversation-context redesign.                                                                                                                                                                           | Implementation complete                     | 447 frontend, 922 non-PostgreSQL and 68 PostgreSQL tests pass above the separate 95 percent line and branch gates; browser acceptance is recorded in the delivery handoff.                                                                                                                               |
| 19     | Deterministic live-demo PDF corpus, specialist ACG matrix and Store/RFI search assurance.                                                                                                                                                                                                                 | Implementation complete                     | 993 backend tests pass with PostgreSQL at 97.62 percent combined coverage; frontend passes at 98.54 percent line and 95.09 percent branch coverage, with a successful production build and visual PDF inspection.                                                                                        |
| 20     | Grounded generation-aware Intelligence Store retrieval, independent search embedding administration and full-corpus RFI/RFA duplicate assurance.                                                                                                                                                          | Implementation complete                     | 1,129 backend tests pass with real PostgreSQL and pgvector at 98.16 percent line and 95.12 percent branch coverage. Live browser checks prove hybrid cited offers, visible-customer duplicate joining and manager RFA discovery.                                                                         |
| 21     | Compact admin command centre, explicit provider/key state, Realtime connection assurance, return navigation and separate aggregate-only admin analytics.                                                                                                                                                  | Implementation complete                     | 507 frontend, 1,072 non-PostgreSQL and 70 real-PostgreSQL tests pass above the separate 95 per cent line and branch gates; static, contract and live browser acceptance checks pass.                                                                                                                     |
| 22     | Customer-controlled product resolution, assured no-match, active-work joining, autonomous policy-constrained JIOC routing, manager intervention, safe tracking and deterministic QC preflight.                                                                                                            | Implementation complete                     | 1,176 backend tests and one intentional skip pass at 98.09 per cent line and 95.12 per cent branch coverage; 518 frontend tests pass at 98.85 per cent line and 95.05 per cent branch coverage.                                                                                                          |
| 23     | Agent-safety hardening for JIOC rollout, routing evidence, bounded LLM output, safe run provenance, outbox replay and authority boundaries.                                                                                                                                                               | Implementation complete                     | Evaluated v2 routing is active for supported local/test use; hosted activation remains explicitly gated.                                                                                                                                                                                                 |
| 24     | Hierarchical organisation units, single-home personnel postings, explicit descendant management, canonical workforce calendars, workflow-derived team Kanban, enhanced work packages, capacity reservations and a balanced 53-person synthetic workforce.                                                 | Implementation complete; activation gated | Migrations 0017 to 0045 provide hierarchy, calendars, workspace operations, assignment and package lifecycle, fixture, backup/recovery and exact-candidate cutover controls. Phase 10 is omitted from the first release. Active authority and routing remain gated on external evidence and an explicit deployment decision. |

## Sprint 24 Hierarchical Workforce Programme

Current phases: **Phases 1 to 9 and the Phase 11 local implementation are
complete, with activation deliberately gated**. Phase 10 is explicitly omitted
from the first release and is non-blocking. The
current-state audit and decision pack are accepted. Phase 1 corrected the
legacy flat-team boundary. Phase 2 added a relational PostgreSQL shadow that
does not influence live access or workflow. Active hierarchy authority remains
blocked until the explicit cutover decision, independent routing approval and
protected release evidence pass.

### Delivery checklist

- [x] Audit flat teams, calendars, route queues, work packages, assignment,
      JIOC capacity use, canonical seed and running local drift.
- [x] Draft the full feature contract, ADR 0049, threat model, migration
      dispositions, user journeys and acceptance matrix.
- [x] Approve the organisation/delivery distinction, exhaustive management
      actions, single-home transfer policy, decision-authority table, privacy
      thresholds, capacity arithmetic, numeric budgets and exercise hierarchy.
- [x] Phase 1: correct current flat-team availability, candidate bounds and
      central authority policy without adding hierarchy.
- [x] Phase 2: add read-only relational hierarchy, one-effective-membership
      constraints, topology history, drift tooling and shadow reconciliation.
- [x] Phase 3: add explicit grants, lifecycle commands, triage/team ownership
      and security-safe authority cutover.
      Grant create/revoke authority and the minimal versioned
      `team_task_ownership` boundary are implemented. Tree lifecycle commands,
      bootstrap, previewed create/edit and safe subtree reparent commands are
      implemented. Single-home membership lifecycle and scheduled exact-boundary
      personnel transfer commands and fail-closed deactivation are implemented.
      The merge command now supports serialisable, explicit-disposition merges
      into an existing successor, including nested child-subtree movement,
      membership replacement, grant revocation, profile/capability movement,
      task movement or cancellation, pending-transfer cancellation and immutable
      topology/ownership/profile history. The split command now creates two or
      more successor units and resolves every named child, membership, grant,
      delivery policy, task and pending transfer in one serialisable operation.
      It preserves fixed-term posting bounds, cancels not-yet-effective postings
      when ended, records immutable histories and rejects stale inventories.
      All command boundaries are exposed through administrator-only,
      CSRF-protected APIs in a distinct non-operational `management` mode. The
      administration UI now provides a navigable hierarchy, selected-unit and
      grant inspection, password-and-nonce bootstrap, delegated authority
      create/revoke, previewed create/edit/reparent/deactivate, current roster
      and membership lifecycle controls, exact-boundary personnel transfer and
      explicit-disposition merge/split workflows. Each destructive workflow
      executes the exact assessed and reviewed payload. Scoped manager views
      and live workflow cutover remain.
- [x] Phase 4: deliver canonical personal/team calendars and profile snapshot.
      Revision `20260803_0028` now provides canonical events, scopes,
      recurrence exceptions, immutable version history and actor-bound command
      evidence. Personal and manager-owned mutations use exact preview hashes,
      serialisable PostgreSQL writes, current account checks and, for manager
      events, fresh home-membership plus exact `calendar:manage` lineage
      validation. Audit/outbox evidence omits note text. The personal seven-day
      profile snapshot and full 90-day agenda can create and cancel
      owner-managed all-day events through the canonical API. Local Compose
      enables the non-operational `management` mode so these features can be
      exercised without switching routing, access or workflow authority.
      Privacy-safe direct-team rows and root-level descendant daily aggregates
      are now available from the unit inspector. They use explicit aggregate
      versus detail actions, 92/31-day windows, 100-row bounds, a stable
      15-minute snapshot and small/incomplete-count suppression. Working
      patterns and a previewed legacy import are now implemented. Migration
      0035 preserves creator and note provenance with stable identities,
      reports invalid/orphaned/colliding rows as blockers and never overwrites,
      dual-writes or activates cutover. Bounded daily and weekly recurrence is
      now expanded consistently in the personal agenda, direct-team rows,
      descendant aggregates, forecasts and reservations. Owners can create,
      edit and cancel a whole series with expected-version and idempotency
      protection. Occurrence exceptions, edit-this, edit-future and timed
      partial-day personal activity are now implemented through migration
      0038. Occurrence keys, replacement content and future-series identities
      are preview-bound and revalidated in the serialisable write; the shared
      reader applies them to calendar and capacity projections.
      Complementary-suppressed child drill-down, cross-source deduplication,
      team commitments, acknowledgement, dispute and notifications are
      implemented through revision 0041.
      The ordinary team page now adds a canonical home/managed workspace
      selector. Home comes only from the one current posting; managed roots
      require independent `organisation:view` and `workspace:view` grants, and
      calendar actions remain separately authorised. Legacy roster/calendar
      content is not treated as canonical managed-team content.
- [x] Phase 5: deliver workflow-leg ownership and enhanced work packages.
      New analyst assignment now commits canonical active team ownership,
      topology/profile snapshots, audit and outbox atomically with the ticket.
      Projection is explicitly enabled only in organisation management or
      active mode, and the synthetic compatibility teams share canonical unit
      IDs, preserving the established workflow when organisation mode is
      disabled.
      Historical active assignments are now reconciled automatically and
      idempotently when management mode starts. Only one-team-per-route records
      with current delivery authority are backfilled; ambiguous, conflicting or
      malformed cases become blocking findings. Reconciliation also creates
      missing historical work packages without replacing existing package or
      participant decisions. Migration 0029 now adds the
      canonical enhanced package, participant, dependency, immutable history,
      command, working-pattern, capacity-exception and reservation ledgers.
      Relational assignment projects every package in the same transaction,
      assigns one accountable analyst deterministically from the explicit
      assignment, and rechecks their sole eligible home posting in the owning
      leaf team. Ticket package completion advances canonical history and
      releases active reservations atomically. Managers with exact current
      `task:assign` lineage can now preview and execute one atomic package plan
      plus personal capacity reservation from the canonical team board. The
      command refines effort, due date and priority, advances package history,
      and writes command, audit and outbox evidence in the same serialisable
      transaction. Reviewed contributor add/end now binds current account,
      single-home posting, package, ownership and exact grant evidence, writes
      immutable command/audit/outbox history and updates My Work immediately.
      Contributor addition may reserve that person's capacity in the same
      transaction; contributor removal releases their live package reservations.
      Reviewed dependency add/remove commands now bind the complete bounded
      graph, exact versions and `task:assign` lineage, reject cross-leg links
      and cycles, and commit immutable evidence atomically. Same-leaf package
      handover now binds authoritative current ticket assignment, exact package,
      participant, reservation and grant versions. It atomically replaces the
      accountable participant, safely disposes of the source reservation and
      records actor-scoped command, audit and outbox evidence. Cross-team
      workflow-leg transfer is a two-manager, work-only proposal and acceptance
      operation in revision 0039. It never moves or cross-posts personnel.
      Cancelling a
      predecessor with live dependants now requires a complete, version-bound
      cancel, unlink or replace disposition for every direct dependant. The
      command locks the bounded graph and records immutable command, history,
      audit and outbox evidence.
- [x] Phase 6: deliver My Work, team/management boards and integrated workspace
      views. A read-only direct-team board is now present in the ordinary
      workspace behind exact `task:view` authority, bounded to 100 allowlisted
      cards with completed work hidden by default. Cards now include bounded
      canonical package summaries. An independently authorised `task:assign`
      grant enables the reviewed plan-and-reserve command without turning the
      board into a second workflow state machine. My Work is now an actor-only,
      keyset-paged package projection with recent completion opt-in. The full
      My Work page now adds status filtering, previous/next paging, card/table
      alternatives and focus restoration. Direct and descendant boards now
      provide keyset paging, team/status/priority/due filters, a table view and
      a 30-day default completion bound (at most 90 days through the API).
      Descendant detail requires a valid `task:view` lineage for each team;
      aggregate-only child authority returns team/status counts without ticket
      identifiers, references, titles, package data or hidden facets; counts
      below five are suppressed. Existing QC/JIOC queues remain authoritative
      rather than being replaced by a second board state machine. Managed
      workspaces expose six authority-dependent tabs: Overview, Board,
      Calendar, People, Capabilities and Settings. Bounded cross-surface
      search, privacy-safe analytics and expiring audited CSV exports are
      implemented through revision 0044.
      Actor-owned saved views, authorised team package templates, opaque
      access-rechecked Store links and the idempotent work-update inbox with
      acknowledgement and personal delivery preferences are implemented. The
      runtime projection handler exists, but automatic lifecycle producers are
      not yet claimed as complete; users must not be promised an update for
      every lifecycle event until those producers have end-to-end evidence.
- [x] Phase 7: deliver conserved capacity, idempotent reservations and
      deterministic recommendations. The first internal reservation store now
      serialises per user, locks package and posting evidence, requires a single
      covering working pattern, unions overlapping unavailable calendar time,
      accounts for current reservations and capacity exceptions, checks the
      package remaining estimate, and supports request-hash idempotent replay.
      Its 15-minute arithmetic is covered independently. Timed events and
      timezone-aware all-day leave now reduce the same physical interval.
      Bounded daily and weekly recurrence preserves local wall time across DST;
      malformed rules, unsupported exception overrides and more than 500
      candidate rows fail closed. Reservation and idempotent replay now
      revalidate exact current `task:assign` lineage in the same transaction,
      and the request hash includes the actor. The management-mode HTTP boundary
      now exposes only their combined previewed operation. Reservation identity
      checks both command key and reservation ID, and package update,
      reservation, history, audit and outbox commit atomically. Migration 0042
      reconciles reservations and participants on package/ticket termination,
      hold, rework, reassignment, account or membership ineligibility and team
      deactivation. Calendar, estimate, deadline, competency and capability
      changes create explicit reforecast or review conflicts instead of silently
      resizing capacity. A startup scan handles time-driven expiry that occurred
      while the service was stopped. Recommendation acceptance now atomically
      updates the ticket, workflow owner, packages, decision/hold state and
      personal reservation. A
      bounded direct-team forecast is available behind exact `task:assign`
      authority and reports only aggregate ready/partial/unknown evidence.
- [x] Phase 8: run the new JIOC capacity context in shadow.
      The relational context is composed only for management plus shadow mode,
      all 40 catalogue teams map to seven delivery leaves, and missing evidence
      fails closed. Its expanded 48-case suite now has a distinct release ID
      which is not approved by default. The suite covers all seven leaves and
      compares conserved minutes with bounded, versioned demand ranges,
      allowing feasibility only when the approved upper bound fits. Independent
      approval remains.
- [x] Phase 9: complete the 53-person cohort, scenario fixtures and local
      48-case activation evaluation. The identity catalogue now contains
      exactly 53 unique fictional personas and preserves the original 16
      numbered-login positions. It includes exactly 24 analysts, distributed
      once each across seven flat compatibility delivery teams as 14 RFA-only
      and ten CM-only analysts. Fresh seed identities and teams use stable
      namespace IDs, and a machine-readable integrity report fails on count,
      duplicate, cross-post or active-leaf shortfall drift. The relational
      exercise manifest now explicitly defines the requested labels, parentage,
      four RFA and three CM leaves, one effective home per persona, exactly 12 active
      eligible RFA and nine active eligible CM analysts, one future RFA joiner,
      one ended RFA analyst, one inactive and membership-suspended CM analyst,
      a non-overlapping historical transfer and 24 working patterns.
      It makes no claim about a real command structure. A local/test-only
      administrator action now previews the entire relational manifest, blocks
      on a foreign root, changed stable row or overlapping local
      posting/pattern, requires fresh password authentication and applies every
      missing row atomically with an idempotent command plus audit/outbox
      evidence. Its separately reauthenticated reconcile command restores only
      reviewed mutable rows addressed by exact fixture identifiers. It neither
      deletes nor modifies local additions, and refuses authority, task or
      immutable-evidence drift. The manifest now
      also supplies three controlled capabilities per delivery leaf, two
      verified competencies per analyst and eight bounded leave, training,
      duty, meeting and private-appointment calendar scenarios. It also grants
      82 stable least-privilege management actions to area managers, leaf leads
      and bounded governance roles. Twenty-four operational tasks now cover all
      seven delivery leaves, 21 active board states and three recent closed
      examples. Their 24 canonical ownership rows and 48 dependent work
      packages include urgent, blocked, review, rework, hold and analysed-CM
      handover cases. PostgreSQL apply/replay, cross-administrator settled
      preview and rollback-on-conflict evidence pass. The task manifest now
      allocates marked work deterministically from active, effective,
      assignment-eligible home postings using working-pattern capacity rather
      than analyst names. Twenty-four differentiated fictional analyst
      profiles, two clearance levels, at least seven ACG combinations and
      explicit idle, loaded, overloaded and unavailable scenarios are present.
      Two bounded reservations and the non-overlapping transfer are persisted.
      A live machine-readable report covers duplicate units, membership
      overlap, ownership, workload concentration, reservations, ACG access,
      clearance, transfer evidence and the inactive account. Independent
      activation approval remains. The 48-case deterministic safety
      and replay metrics pass under their distinct unapproved release ID.
- [x] Phase 10 decision: omit the external calendar connector from the first
      release. The canonical internal calendar is complete without it. A future
      connector remains optional and requires its own credential, consent,
      egress, replay and deletion evidence. This omission does not block the
      core release.
- [ ] Phase 11: complete bounded-context cutovers, runbooks, browser journeys,
      protected CI and the release security gate.
      An admin-only read-only report now checks bounded database evidence and
      always keeps routing approval, browser, protected-CI and security evidence
      blocking until separately recorded. Its plain-language panel has no
      activation or approval controls.
      Eight dedicated real-PostgreSQL browser journeys now prove the readiness
      panel, recurring-calendar lifecycle and privacy, My Work,
      direct-manager planning, ancestor
      suppression/detail denial, JIOC no-assignment authority and QC queue
      continuity. Ten established secure-workflow journeys also pass from
      request creation and assignment through approval, QC release and
      controlled download. Protected CI, independent approval and the explicit
      active-authority cutover decision remain release gates.
      The release-gated cutover vertical now records an immutable exact
      candidate, distinct reauthenticated approvals and three ordered
      writer-fenced slice checkpoints. Active composition fails closed unless
      current schema, parity, routing, protected-check and security evidence
      match the fully approved manifest. This implementation does not create
      external approvals or activate authority by default. Phase 11 remains
      open until real protected-CI, independent security and deployment
      approvals are recorded for a scheduled release.
      Coordinated logical backup and restore includes the Sprint 24 tables
      through revision 0045, exact row-count and COPY digests, a source writer
      fence held through promotion, authority replay checks, session
      invalidation and failed-target quarantine. The scheduled representative
      PostgreSQL performance gate creates 1,000 units, 10,000 memberships,
      50,000 calendar events and 10,000 cards, records 20 warm samples per
      query and emits a versioned JSON report against fixed p95 budgets. It is
      scheduled/manual evidence, not a PR-blocking production endpoint SLO or
      an externally approved release result.

### Dependencies and decision blockers

- Preserve the current ticket state machine, manager approval, QC authority,
  ACG/clearance policy, session revocation, audit/outbox and Store object-access
  boundaries.
- PostgreSQL must be the transactional authority for hierarchy, grants,
  canonical events, task ownership and reservations; JSON compatibility is a
  read-only projection during migration, not a second writer.
- Approve the exercise-only parentage for Defence Intelligence, DI Joint User,
  DI NCGIA, MIS, UKSF, SAS, SBS, SRR, 18SR, 14SR, PAGC and 4 RANGERS. Code must
  not assert a real command structure.
- Approve the explicit direct/descendant action matrix and who may accept a
  receiving team. Parentage alone grants nothing.
- Approve WIP limits, demand-estimate ownership, single-home personnel transfer
  policy, service levels, small-cohort suppression and privacy categories.
- Phase 10 is omitted from the first release. Internal calendar completeness
  does not depend on an external provider, so this is not a release blocker.

### Principal risks and mitigations

| Risk                                                           | Mitigation and release evidence                                                                                         |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Parent hierarchy broadens intelligence access                  | Separate persisted management grants from ACG, clearance and ticket policy; descendant IDOR suite                       |
| Legacy rollback restores route-wide manager authority          | One relational authority per slice; after policy cutover retain new policy, freeze incompatible writes and roll forward |
| Legacy or concurrent overlapping postings manufacture capacity | PostgreSQL non-overlap constraint, single-home migration disposition, exact-boundary transfers and property tests       |
| Personnel or work transfer leaves source authority behind      | Atomic named-work disposition, participant revocation, reservation replacement and blocked incomplete transfers         |
| Concurrent managers double-book an analyst                     | Serialisable transaction, canonical locks, unique idempotency key and PostgreSQL race tests                             |
| Calendar exposes absence details                               | Coarse teammate projection, explicit detail grant, `<5` aggregate suppression and privacy browser journeys              |
| Board becomes a second state machine                           | Deterministic state/card oracle and existing command endpoints only                                                     |
| Synthetic expansion preserves corrupt local drift              | Stable fixture manifest, preview-only reconciliation, quarantine and non-destructive local additions                    |
| Agent overreaches into team/person assignment                  | Route-only automation, advisory deterministic team ranking, human team acceptance and human named assignment            |

### Evidence map and next action

- Feature and implementation contract:
  [hierarchical teams, workforce calendars and task boards](specs/hierarchical-teams-workforce-calendars-and-task-boards.md).
- Accepted architecture decision:
  [ADR 0049](adr/0049-hierarchical-organisations-and-canonical-workforce-capacity.md).
- Planned security controls:
  [hierarchical workforce threat model](threat-model/hierarchical-teams-workforce-calendars-and-task-boards.md).
- Current implemented baseline:
  [teams, profiles and calendars](specs/teams-profiles-calendars.md).

Canonical My Work and the direct-team manager capacity forecast are now
implemented. Forecasts are aggregate, advisory, exact-`task:assign` authorised
and fail to partial or unknown when identity, posting or capacity evidence is
incomplete. Next action: replace legacy JIOC headcount with the versioned
shadow-only forecast context, then complete the relational people projection
and assignment eligibility model before any active cutover.
Child-level complementary suppression and the scoped relational people
projection remain prerequisites
for descendant drill-down and full legacy workspace removal.
Restructure dependency inventories must be extended when calendar, reservation
and saved-view tables arrive in their own phases.
Do not switch queue mutations, calendars or the ticket workflow to hierarchy
authority until the remaining ownership, package, capacity and cutover gates
exist. The current assignment integration records canonical ownership but
continues to use the established assignment authorisation policy.

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
  [18 July evidence](security/SECURITY_REVIEW_REMEDIATION_2026-07-18.md);
  [ADR 0038](adr/0038-atomic-identity-security-state-and-session-retention.md)
  and [ADR 0039](adr/0039-protected-workflow-draft-authorisation.md) record the
  identity and protected-draft boundaries.

## 20 July 2026 Agent-Safety Hardening

Status: complete. Independent code-quality and security reviews were remediated.
The final recorded full backend and frontend suites passed with both line and
branch coverage above 95 per cent; the development story retains the
point-in-time test counts for each 20 July slice.

### Candidate Checklist

- [x] Prove `disabled` invokes no capability agent and only refers to human
      review, while `shadow` records
      comparison evidence without route side effects, and only an explicitly
      allowlisted `active` release may apply deterministic transitions.
- [x] Prove routing fails closed to clarification or human review for
      conflicting or negated signals, stale or missing context, restrictions,
      unavailable or missing candidate-team capacity and unmet evaluation evidence.
- [x] Approve and activate the allowlisted `jioc-routing-policy-v2` release for
      synthetic local/test use after conflict, stale-context, capacity and authority
      cases passed. Hosted activation remains separately gated.
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

- Before real or sensitive data: approved classification, DLP/redaction and
  egress policy; provider/model/region allowlists; retention; a representative
  human-labelled corpus; calibration, drift and rollback evidence; and a
  decision on any richer provider context.
- LiteLLM connectivity sits behind a deployment-managed URL, encrypted scoped
  key, bounded discovery and deterministic controllers; production still needs
  explicit aliases, workload identity, egress/retention approval and route
  evaluation under ADR 0041 and the LiteLLM threat model.
- Residual risks are cumulative across the linked threat models:
  process-local availability, third-party parsers without process isolation,
  new guarded-write drift and provider/real-data governance.
- Keep the evaluated release `active` only for synthetic local/test use with
  `disabled` as the rollback switch; hosted use requires labelled evidence,
  real-data governance and a separately reviewed canary.

## 27 July 2026 Workflow review remediation

All eight defect groups are fixed under the
[remediation contract](specs/workflow-review-remediation-2026-07-27.md) without
state-machine edge changes. Workflow-wide push notifications and any
incomplete-search override remain product decisions.

## 22 July 2026 Sealed-scan remediation

The earlier findings and follow-up scan are fixed and verified, covering exact
sessions and authority, visibility, lock order, atomic audit, parser budgets
and cancellation-safe submission. Authorised staging remains open under the
[22 July contract](specs/security-scan-remediation-2026-07-22.md).

## 20 July 2026 Bounded Advisory Reasoning

Status: complete and verified for the supported local/test boundary.

- [x] Implement the feature spec and ADR 0040 with deterministic authority.
- [x] All quality/security gates and independent reviews passed: 1,432 backend
      tests (one intentional skip) at 98.13/95.07 and 533 frontend tests at 98.65/95.05.
- Risk: remote use remains blocked pending labelled evidence and real-data approval.

## 23 July 2026 Architecture Atlas

- Added 32 implementation-anchored user, workflow, technical and operational
  diagrams, with repository-wide Mermaid parsing.
- Local QC notification intents need the hosted dispatcher. Recovery reconciles
  Store assets only; retained draft bytes block validation and grounded indexes
  require a verified post-restore rebuild.
- Current search-operations limitation: inactive ready generations are retained,
  with no authorised operator rollback, retirement state or cleanup policy.
- JIOC Team Members and Managers share exception review; Managers own on-loop
  oversight and intervention. [ADR 0043](adr/0043-jioc-human-review-and-manager-oversight.md)
  covers Agent evidence, attention filtering and role-specific seeded journeys.

## 2 August 2026 Retrieval readiness and richer exercise products

- [x] Retain natural provider labels, fixed provenance and explicit cloud activation.
- [x] Automatically rebuild local retrieval and clear all 35 legacy asset warnings.
- [x] Generate and visually verify eight-page operational exercise reports.
- [x] Activate the verified Gemini key and simplify automatic-update status for non-technical users.

## 2 August 2026 Customer search recovery and outcomes

- [x] Preserve assurance without stale warnings; require reject-all feedback before refined search, JIOC tasking or outcome closure.

## 2 August 2026 Intelligence Store browse and search improvements

Status: implemented and verified on `main`; changes are uncommitted in the working tree.

- [x] Add server-side `sort` (`relevance|title|coverage`) on `GET /api/v1/store/products`, applied to the whole matched set before paging so a sort choice holds across pages; previously no sort parameter existed and the web UI reordered only the current page.
- [x] Add `facets.counts` to the store search response, counting visible products behind each product type, region and tag over the access-scoped, structurally-filtered set, alongside the existing ordered value lists, keeping the response backward compatible.
- [x] Add one-shot query relaxation: a multi-term text query that returns nothing is retried with its terms joined by `OR`, with the response carrying `relaxed: true` while match reasons stay derived from the query the operator typed.
- [x] Move web store search state into the URL so a search survives navigation, refresh, bookmarking and browser Back.
- [x] Raise page size from 6 to 24 with numbered pagination, add a clickable counted facet rail, and lead result cards with classification marking and status badge, plain-date coverage, asset make-up and plain-language match explanations.
- [x] Request owner-team scoping from the server rather than filtering client-side.
- [x] Fix an out-of-range page rendering a backwards range ("Showing 49-17 of 17"), and fix "Back to store" losing the applied search.

### Deferred Scope

Identified during this work but not implemented:

- Related products / more-like-this: product embeddings and an HNSW index already exist, but no endpoint exposes them.
- Store-facing page-cited passage excerpts: the chunk index provides these to RFI search only.
- Product edit, archive and asset-management endpoints: `product:update_metadata`, `product:manage_assets` and `product:archive` are granted to roles but no endpoint enforces them.
- `createdAt`, `updatedAt`, `createdBy` and `boundingBox` are stored but stripped by the response presenter.
- Reuse signals per product exist in the RFA and Collection analytics endpoints but are not surfaced in the store.
- No audit event on normal product view, preview or download; only break-glass is audited, and no watermarking exists.

## 2 August 2026 Intelligence Store projects and subscriptions

Status: implementation and local quality-gate verification complete.

- [x] Separate Store navigation into Discover, My Library, Projects and Subscriptions.
- [x] Add private Library folders as a dedicated workspace while preserving the
      existing per-user save and organise model.
- [x] Add purpose-bound projects with owner-controlled membership, authorised
      products, notes, intelligence questions, archive/restore and activity.
- [x] Recheck current product policy whenever project evidence is returned and
      remove product-identifying activity when that product is not visible.
- [x] Add private reusable search subscriptions with manual, daily or weekly
      review cadence, pause/resume, current-result opening and no external alerts.
- [x] Add access-controlled ACG subscription scopes and optional keyword,
      region, product-type, tag, source-type and date refinements. Revalidate
      active ACG membership on save and search, including after access changes.
- [x] Add a project return path and product-to-project control to product detail.
- [ ] External delivery, scheduled execution, generated briefing documents,
      map workspaces, comparison tools and workflow tasking remain deferred.

Verification: 1,814 backend tests passed with one intentional compatibility
skip at 98.36 per cent line and 95.44 per cent branch coverage against real
PostgreSQL. All 628 frontend tests passed at 98.73 per cent line and 95.03 per
cent branch coverage. Ruff, mypy, ESLint, Prettier, TypeScript, production
build, architecture, file-length, documentation, Mermaid and OpenAPI contract
checks passed.

## 3 August 2026 access-controlled ACG subscriptions

Status: implementation and quality-gate verification complete.

- [x] Offer only active ACG memberships in the subscription interface.
- [x] Allow a subscription to follow up to 12 selected ACGs and refine the
      results with keywords or phrases and the existing Store filters.
- [x] Treat an ACG selection only as a restrictive search scope, never as an
      authority grant. Reject unknown, inactive and ungranted identifiers.
- [x] Recheck current membership when opening results and visibly flag a saved
      subscription whose selected ACG access has changed.
- [x] Update the feature specification, ADR, threat model, API contract and
      user guide.

Verification: 1,816 backend tests passed with one intentional compatibility
skip at 98.37 per cent line and 95.47 per cent branch coverage, including the
real PostgreSQL transaction suite. The full frontend suite passed at 98.73 per
cent line and 95.07 per cent branch coverage.
