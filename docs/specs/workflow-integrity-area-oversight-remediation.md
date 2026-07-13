# Workflow integrity, area management and JIOC oversight

## Status

Implementation delivered (2026-07-12). The full eight-role real-browser
acceptance evidence remains outstanding and is carried into Sprint 17. Delivery
evidence is recorded in `docs/DEVELOPMENT_STORY.md`; remaining verification is
tracked by `docs/security/SECURITY_REPAIR_AND_HARDENING_PLAN.md`.

## Purpose

Close the July workflow audit findings without weakening the local-first
runtime. RFA and CM managers operate across every team in their respective
area, while the selected organisational team remains authoritative for
candidate membership, availability and assignment records. JIOC gains a
read-only, end-to-end operational view of teams, analysts and task load.

## Required behaviour

### Workflow state and rework

- Structured information supplied after JIOC clarification resumes JIOC review
  when the intake is complete; it must not repeat prioritisation or RFI search.
- Manager and QC rework require a draft version created after the latest return
  or rejection before resubmission.
- Analyst task list and detail endpoints use the same visible workflow states.
- Credential resets either complete fully and return the temporary credential,
  or restore the original credential, sessions and login-attempt state.
- Final release audit evidence must not claim success for a release that was
  compensated and rolled back.

### RFA and CM area management

- An RFA Manager can assign work to every active RFA team and an active member
  of the selected team. A CM Manager has the equivalent capability for CM.
- Team selection uses an immutable team ID. Display names are derived data.
- Candidate search and availability are scoped to the selected team.
- Assignment, reassignment, manager review and queue access enforce the route
  area and persisted team ownership at the object boundary.
- One to five analysts may share a task. An analyst may hold multiple tasks.

### JIOC oversight

- JIOC can open an oversight workspace covering all workflow states.
- The workspace reports ticket counts by state and route, active teams,
  analysts, availability and live task allocations.
- It exposes task-level references and ownership summaries without granting
  JIOC product-content, analyst-note or draft-edit permissions.
- Oversight data is bounded and derived server-side from authorised workflow
  and team projections.

### ACG applications and delegated administration

- Every active authenticated user can open an Access Groups workspace, browse
  active ACGs and see their membership and application status.
- A non-member can submit one pending application per ACG with a bounded
  justification, and can withdraw it while it is pending.
- Each active ACG has one to eight administrators. An administrator may hold any
  application role and does not gain product membership merely by administering
  the group.
- Platform administrators manage the ACG-administrator roster using active user
  identities. The one-to-eight administrator invariant is enforced atomically;
  an active ACG cannot lose its final administrator.
- An ACG administrator can list and approve or reject pending applications only
  for ACGs they administer. A platform administrator has the same decision
  capability for support and initial setup.
- No actor can approve or reject their own application. Approval atomically adds
  membership and records the decision; rejection requires a reason.
- Duplicate, stale and already-member applications fail without changing group
  membership. Application and decision events are audited without exposing the
  applicant's justification in unrelated logs.
- The workspace shows ordinary users their own applications and shows an
  additional bounded review queue only when they administer at least one ACG.

### Interface recovery and accessibility

- Store Managers can search active user identities for ACG membership without
  receiving user-administration permissions.
- High-impact controls lock while pending and show success or failure.
- Customer-entered text is cleared only after a successful mutation.
- Calendar labels use the real local date, not the first visible day.
- Unknown routes and render failures use a branded recovery boundary.
- Queues, direct links, availability and directories distinguish loading,
  empty and error states.
- Dialogs and popovers manage initial focus, Escape and focus restoration.

### Local operation and migration guidance

- Local PostgreSQL binds to loopback after the documented startup command.
- Alembic upgrades tolerate the legacy runtime-created audit table and leave
  the schema at head.
- Reset procedures keep PostgreSQL metadata and object bytes consistent and
  never synthesise replacement bytes for user-created products.
- Compose waits for API readiness before declaring the web service ready.
- Node and pnpm prerequisites match the locked toolchain.
- GCP and Kubernetes documents state their real readiness gates, required
  environment settings and unsupported production boundaries.

## Verification

- Regression tests cover every workflow and permission boundary above.
- Backend and frontend line and branch coverage remain at least 95 percent.
- Ruff, mypy, ESLint, Prettier, TypeScript, contracts, dead-code, security
  policy, production build, Compose and file-line checks pass.
- Real-browser walkthroughs cover Customer, JIOC, RFA Manager, CM Manager,
  Analyst, QC, Store Manager and Administrator recovery paths.
