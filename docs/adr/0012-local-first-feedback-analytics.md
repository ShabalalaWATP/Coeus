# ADR 0012: Local-First Feedback Analytics

## Status

Accepted.

## Context

Sprint 11 needs feedback submission, role dashboards, product reuse analytics
and trend insights before the persistent database and deployment phases. The
implementation must stay local-first, use only synthetic records and avoid
coupling dashboard routes directly to ticket internals.

## Decision

Implement Sprint 11 as a service layer over existing in-memory aggregates:

- `FeedbackAnalyticsService` owns feedback submission, dashboard scoping,
  metrics and product reuse aggregation.
- `TrendsAnalysisAgent` produces deterministic local insights from ticket,
  feedback and reuse records.
- Feedback submissions are immutable ticket-level records, while feedback
  requests move from `requested` to `submitted`.
- Analytics endpoints expose separate admin, RFA and collection dashboard
  contracts but share the same service and response model.

Dashboards use existing permissions: requesters need `feedback:create`, RFA and
collection managers need `analytics:view_team` plus their route review
permission, and administrators need `analytics:view_global`.

## Consequences

- Sprint 11 remains deterministic and runnable without cloud services,
  external models or real telemetry.
- The route layer stays thin and can be backed by persistent repositories later.
- Analytics are scoped from current in-memory ticket visibility and approved
  route decisions, so production storage must preserve equivalent access
  filters.
- Deterministic trend analysis is intentionally explainable but not a substitute
  for a production analytics pipeline.
