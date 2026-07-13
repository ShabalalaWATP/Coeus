# Assigned QC Reviewer Self-Claim

## Status

Implemented and locally verified for Sprint 17. Protected GitHub verification
passes on the final substantive candidate.

## Purpose

Close the remaining draft-audience gap without removing the shared Quality
Control queue. QC managers may see only non-sensitive queue summaries until one
eligible reviewer atomically claims a submission. Full ticket and draft detail,
approval and rejection then belong only to that reviewer.

## Behaviour

- The queue lists every ticket in `QC_REVIEW` using only its opaque ticket ID,
  reference, workflow state and claim status.
- Claim status is `available`, `claimed_by_you` or `claimed`. The queue never
  names another reviewer or includes requester, question, area, draft, asset,
  manager-note or decision content.
- An eligible QC manager claims an available item with a CSRF-protected action.
  The claim and audit event commit atomically using ticket compare-and-swap.
- Repeating a claim by the same reviewer is idempotent. Competing reviewers get
  one winner and a non-destructive `409 qc_already_claimed` response.
- A reviewer who authored any draft or holds an active analyst assignment may
  not claim, approve or reject the ticket.
- Full detail, approval and rejection require the active assignment. Direct
  URLs and multi-role permissions cannot bypass this check.
- The assigned reviewer may release their claim deliberately. Release is
  audited and returns the item to the shared queue without changing workflow
  state or content.
- A rejection retains the reviewer relationship through `REWORK_REQUIRED` and
  resubmission, so revised work returns to the reviewer who requested it.
- Approval or any transition outside `QC_REVIEW` and `REWORK_REQUIRED` revokes
  effective QC draft authority even if the historical reviewer ID remains on
  the ticket for auditability.

## Persistence And Audience

- `TicketRecord` owns the optional reviewer ID and claim timestamp. Defaults
  preserve legacy decoding and N-1 readers ignore the additive fields.
- Memory/file mode performs ticket compare-and-swap and required audit
  confirmation under one repository lock, rolling back on confirmation failure.
- Hosted PostgreSQL uses the existing workflow transaction to commit the ticket,
  canonical hash, audit and derived draft-audience rows together.
- While the assignment is active, every linked draft Store product receives a
  `quality_control` audience row for the reviewer. Claim release and lifecycle
  changes remove that authority through the same projection derivation.
- Reconciliation derives expected QC rows from the ticket, is idempotent and
  treats legacy unclaimed tickets as having no QC audience.

## Compatibility

- `GET /api/v1/qc/queue` retains its existing `products` field for full products
  assigned to the current reviewer and adds `items` for all safe summaries.
- Existing approve and reject clients may implicitly claim an available item
  before acting. They still cannot act on another reviewer's item.
- The web application uses explicit claim and release controls and never treats
  an unclaimed summary as product detail.
- Backend and frontend must be deployed together. Rolling back to a version
  that lacks assigned-detail guards is security-invalid and requires roll-forward.

## Acceptance Evidence

- Queue responses contain no sensitive fields for unclaimed or other-claimed
  submissions.
- Memory and PostgreSQL races produce exactly one claimant and one claim audit.
- Audit failure leaves no reviewer assignment or draft-audience authority.
- Assigned reviewers can read linked drafts subject to normal ACG and clearance
  checks; unrelated QC managers cannot search, read or obtain asset grants.
- Claim release, approval and other terminal transitions revoke prior draft
  authority, including at asset-token redemption.
- Rejection and resubmission preserve the same reviewer and intended workflow.
- API, frontend, OpenAPI, N-1, migration, coverage, browser and security gates
  remain green with at least 95 percent line and branch coverage.
