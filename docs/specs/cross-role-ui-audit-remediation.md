# Cross-role UI audit remediation

## Purpose

Resolve the July 2026 cross-role interface audit findings so that customers,
operators, analysts, quality-control staff, team managers and administrators
can understand the current record, the next required action and the effect of
each mutation. Mobile navigation is explicitly excluded from this remediation.

## Required outcomes

### Workflow integrity

- Manager approval shows the submitted analyst draft, linked products, assets,
  work packages and working context before approval or return.
- QC approval requires deliberate completion of each check, an explicit ACG
  choice and explicit release metadata. Bulk completion is removed.
- Irreversible or high-impact actions are locked while their request is pending.
- JIOC cannot approve a route until capability checks have produced a current
  recommendation.
- Ticket-specific form state resets whenever the selected ticket changes.

### Customer requests

- Existing-request routes render a loading boundary and cannot create or mutate
  a different request before the requested ticket is loaded.
- Intake fields distinguish unchanged, set and explicitly cleared values.
- Feedback is submitted from a form bound to one visible feedback request.
- Dashboard metrics are mutually exclusive and derived from workflow state.
- Product offers and similar-request actions appear only in relevant states;
  later states show concise outcomes rather than dead controls.
- Request history uses readable event labels, timestamps and actor attribution.
- The journey dialog manages focus, traps keyboard navigation and restores focus.

### Analyst and manager operation

- Shared tasks show all assigned analysts and work-package ownership or shared
  responsibility clearly.
- Assignment candidates include profile, specialism and availability context.
- Structured team selection replaces arbitrary team-name text where catalogue
  data is available; work packages use explicit repeatable fields.
- Disabled primary actions explain their unmet prerequisites.
- Synthetic metadata-only asset fields are labelled honestly and cannot imply a
  file was uploaded.
- Dense queues prioritise actionable tickets and preserve visible selection.

### Administration, teams and profiles

- ACG membership uses searchable user identities rather than pasted UUIDs.
- User administration supports search and role/status filters with per-row save
  state and visible success feedback.
- Destructive or high-impact changes require confirmation or provide undo where
  appropriate; rejection reasons are bound to the selected request.
- Team member candidate caching is scoped by team.
- Every user can edit their own profile; loading and errors cannot overwrite a
  stored profile with blank values.
- Local calendar dates remain correct across time zones and daylight-saving
  boundaries.
- Availability counts each person once per category.
- Calendar presentation follows the backend latest-entry-wins rule and supports
  replacement/editing across the backend-supported planning window.
- Store-manager onboarding explains ACG requirements and avoids an unexplained
  empty workspace.

### Accessibility and language

- Command navigation uses combobox/listbox semantics and keyboard selection.
- Popovers expose expanded state and controlled elements.
- Selected records use visible and semantic selected/current state.
- Tooltip-only rationale is available through an accessible disclosure.
- Internal UUIDs, enum strings and machine reason tags are replaced with human
  labels where they are not required for support diagnostics.

## Verification

- Behaviour tests cover every corrected defect and pending/error boundary.
- Frontend and backend line and branch coverage remain at least 95 percent.
- Formatting, linting, type checks, contracts, security-policy checks and the
  350-line source limit pass.
- Live walkthroughs cover customer, JIOC/RFA/collection manager, analyst, QC,
  administrator, store manager and team-member views.
