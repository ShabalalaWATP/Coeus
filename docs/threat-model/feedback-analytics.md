# Threat Model: Feedback And Analytics

## Scope

Requester feedback submission, RFA/Collection workflow analytics, aggregate-only
admin platform analytics, product reuse analytics and deterministic Trends
Analysis Agent insights.

## Assets

- Feedback requests and submitted feedback.
- Ticket route, dissemination, search and feedback records.
- Product reuse counts and average requester ratings.
- Role-scoped analytics dashboard data.
- Generated trend insight summaries.
- Aggregate account, sign-in, AI configuration, search, voice and audit counts.

## Threats And Controls

| Threat | Control In Sprint 11 |
| --- | --- |
| User submits feedback for another requester. | Feedback lookup requires `feedback:create` and matches the request requester ID to the actor. |
| User submits duplicate feedback. | Feedback requests move to `submitted`; repeat submissions return `feedback_already_submitted`. |
| Customer accesses admin or team analytics. | Analytics endpoints require explicit `analytics:view_global` or `analytics:view_team` permissions. |
| RFA manager reads collection-only analytics. | Team dashboards require both `analytics:view_team` and the matching route review permission. |
| Dashboard metrics leak hidden product titles. | Product reuse is derived from tickets visible to the dashboard audience. |
| Admin analytics exposes intelligence detail or identifiers. | `/analytics/admin/platform` has a separate response model containing counts and safe configuration state only. Deprecated `/analytics/admin` returns zero metrics and empty collections. Neither implementation returns ticket, product, query, title, reference, username, actor ID or audit metadata values. |
| Admin activity metrics reveal individual behaviour. | Audit events are reduced server-side to counts and distinct-user totals. Raw actor IDs and metadata remain confined to the separately permissioned audit log. |
| Retention-bounded activity is mistaken for complete history. | The response declares the 30-day window, earliest retained event and whether the audit retention limit has been reached. |
| Process counters are mistaken for durable billing data. | Provider admission values are labelled as process-lifetime operational signals. Chat turns are not labelled as provider calls, tokens or cost. |
| Feedback text stores real operational data. | Public-repo fixtures and tests use `MOCK DATA ONLY`; production needs moderation and retention controls. |
| Trend summaries overstate model certainty. | Sprint 11 uses deterministic local confidence values and exposes them with each insight. |

## Residual Risks

- Feedback moderation, rate limiting and abuse detection are not implemented in
  the local-first sprint.
- Analytics are computed in process from in-memory records. Production needs
  database-backed scoping, retention policy and query performance review.
- Provider token, cost, latency and embedding-call analytics are not yet
  available. They require a durable low-cardinality provider usage projection
  that never stores prompts or intelligence content.
- The Trends Analysis Agent is deterministic and explainable, not a substitute
  for validated statistical analysis.
