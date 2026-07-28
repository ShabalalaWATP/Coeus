# Workflow Review Remediation, 27 July 2026

A full review of the shipped request workflow on `main` (state machine, JIOC
routing and oversight, intake to consent, production to release, frontend
surfaces) confirmed a set of defects. This contract records the accepted
findings and the shipped fixes. No state-machine edge changed.

## Fixed defects

1. **Terminal-state capacity leak.** `TERMINAL_TICKET_STATES` predated the
   outcome-loop closures, so `CLOSED_REQUIREMENT_MET`,
   `CLOSED_REANALYSIS_DECLINED`, `CLOSED_UNANSWERED` and
   `CLOSED_JOINED_EXISTING_WORK` consumed admission capacity forever. The set
   is now derived from the state machine (states with no onward transition),
   the local shadow-schema backfill repairs projected rows, and Alembic
   migration `20260727_0015` backfills hosted rows so startup reconciliation
   cannot fail.
2. **Routing-phase `INFO_REQUIRED` flavour confusion.** The resume
   discriminator only recognised `route_recommendations`, so clarification
   tickets reached through a deferred referral never resumed, and a chat
   reply (the channel clarification questions are delivered on) regressed
   any routed ticket to `DRAFT_INTAKE`. A shared
   `routing_history_present` predicate (recommendations, agent decisions,
   manager decisions or clarification handoffs) now governs intake edits,
   added information and chat; chat replies resume to `JIOC_REVIEW` with a
   `route_assessment_resumed` timeline entry. Safety-flagged messages are
   not treated as clarification answers.
3. **QC rework deadlock for uploaded versions.** Rework resubmission now
   re-pins the immutable manifest of the exact resubmitted version, so the
   `manager_approved_version` preflight check passes for uploaded external
   products. First-round behaviour is unchanged.
4. **Deactivated-account strands.** Analyst reassignment is permitted in
   `REWORK_REQUIRED` (state unchanged), and a QC claim whose holder is no
   longer an active, QC-eligible account can be taken over by an eligible
   reviewer (`qc_claim_transferred`, audited).
5. **Untested chunk-index access predicates.** `SEARCH_CHUNKS_SQL` is the
   sole retrieval-time access control on the Postgres grounded-search path.
   A structural tripwire test and a Postgres behavioural test now fail if
   the ACG, clearance or status predicates stop gating either retrieval leg.
6. **Requester lockout at release.** The release-time block now fails with
   `requester_access_lost` (409) instead of a misleading 404, and the QC
   detail carries an advisory `requesterAccessWarning` computed from the
   draft metadata.
7. **Re-analysis version integrity.** A re-analysis order requires a revised
   draft before resubmission; the identical version can no longer be
   re-released unchanged.
8. **Smaller defects.** Oversight availability now uses the UTC calendar day
   used by routing capacity; hold-resume validates the restored state against
   the state machine and rejects corrupt records with
   `intervention_state_invalid`; the intervention allowlists are pinned to
   the state machine by test; the routing handoff run-slicing no longer
   hardcodes the review run count; empty-string environment API keys read as
   not configured; the frontend no longer offers Cancel on legacy
   `RFI_NO_MATCH`, and journey-stage and dashboard state maps cover the
   re-analysis and outcome closure states.

## Deliberately out of scope

- Workflow-wide notifications for analysts, managers and QC remain queue
  driven; adding push notifications is a product decision, not a defect fix.
- No customer override was added for `RFI_SEARCH_INCOMPLETE`: degraded search
  deliberately cannot produce a definitive no-match, so the exit remains
  retry, cancel or index repair.

## Verification

Backend and frontend suites, both coverage gates, mypy, ruff, ESLint,
Prettier, TypeScript, the OpenAPI contract check, the line-limit gate and the
Postgres migration and concurrency harness all pass with the fixes applied.
