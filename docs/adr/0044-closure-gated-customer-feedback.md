# ADR 0044: Closure-Gated Customer Feedback

## Status

Accepted.

## Context

ADR 0012 established immutable product feedback records and role-scoped
analytics. QC release prepares a feedback request at the same time as it
disseminates a product, but the customer must still decide whether the product
meets the requirement. A rejection can start manager and JIOC re-analysis
decisions, so accepting feedback during this period conflates an active outcome
decision with retrospective satisfaction feedback.

The customer dashboard also needs to retain historical requests without letting
them dominate current work.

## Decision

- Keep feedback requests attached to ticket aggregates and prepared during
  release, preserving the existing transactional release boundary.
- Treat the request as pending internal state until its ticket reaches a state
  whose value begins with `CLOSED_`.
- Enforce the closure rule when listing and submitting feedback. The service,
  not the client, owns this rule.
- Keep cancelled tickets in the collapsed dashboard archive but do not make
  them feedback-eligible because they have no completed outcome to assess.
- Present pending feedback sequentially and translate the three customer-facing
  outcome choices to the existing 1-to-5 analytics scale.
- Retain the stored `follow_up_requested` field for compatibility, but omit it
  from the customer form. The closure workflow already resolves unmet work.

## Consequences

- Feedback measures a completed outcome rather than an interim dissemination.
- API clients cannot submit early by bypassing the browser.
- Existing persisted feedback requests become available automatically when
  their ticket closes, so no migration or duplicated closure hooks are needed.
- Analytics retain their established schema and historical records.
- Closed and cancelled requests remain discoverable without competing with the
  active register.

## Related decisions

- [ADR 0012: Local-first feedback analytics](0012-local-first-feedback-analytics.md)
- [ADR 0022: JIOC routing and QC-owned release](0022-jioc-routing-and-qc-release.md)
