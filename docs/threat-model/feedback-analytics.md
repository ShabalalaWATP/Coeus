# Threat Model: Feedback And Analytics

## Scope

Sprint 11 requester feedback submission, admin/RFA/collection analytics
dashboards, product reuse analytics and deterministic Trends Analysis Agent
insights.

## Assets

- Feedback requests and submitted feedback.
- Ticket route, dissemination, search and feedback records.
- Product reuse counts and average requester ratings.
- Role-scoped analytics dashboard data.
- Generated trend insight summaries.

## Threats And Controls

| Threat | Control In Sprint 11 |
| --- | --- |
| User submits feedback for another requester. | Feedback lookup requires `feedback:create` and matches the request requester ID to the actor. |
| User submits duplicate feedback. | Feedback requests move to `submitted`; repeat submissions return `feedback_already_submitted`. |
| Customer accesses admin or team analytics. | Analytics endpoints require explicit `analytics:view_global` or `analytics:view_team` permissions. |
| RFA manager reads collection-only analytics. | Team dashboards require both `analytics:view_team` and the matching route review permission. |
| Dashboard metrics leak hidden product titles. | Product reuse is derived from tickets visible to the dashboard audience. |
| Feedback text stores real operational data. | Public-repo fixtures and tests use `MOCK DATA ONLY`; production needs moderation and retention controls. |
| Trend summaries overstate model certainty. | Sprint 11 uses deterministic local confidence values and exposes them with each insight. |

## Residual Risks

- Feedback moderation, rate limiting and abuse detection are not implemented in
  the local-first sprint.
- Analytics are computed in process from in-memory records. Production needs
  database-backed scoping, retention policy and query performance review.
- The Trends Analysis Agent is deterministic and explainable, not a substitute
  for validated statistical analysis.
