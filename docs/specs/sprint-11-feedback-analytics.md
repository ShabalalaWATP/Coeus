# Sprint 11 Spec: Feedback And Analytics

## Scope

Add requester feedback submission and local-first analytics dashboards over the
records produced by prior sprints. Sprint 11 starts from feedback requests
created after QC dissemination and produces role-scoped operational analytics
for administrators, RFA managers and collection managers.

## In Scope

- Feedback request listing for requesters.
- Feedback submission with rating, comment and follow-up request flag.
- Admin analytics dashboard.
- RFA analytics dashboard.
- Collection manager analytics dashboard.
- Product reuse analytics from disseminations, accepted offers and feedback.
- Deterministic Trends Analysis Agent insights.
- Frontend feedback panel on the request workspace.
- Frontend routes `/admin/analytics`, `/rfa/analytics` and
  `/collection/analytics`.

## Out Of Scope

- Persistent analytics warehouse tables.
- Production event streaming, BI tooling or cloud dashboards.
- Feedback moderation, throttling and abuse automation.
- External model calls for trend analysis. Sprint 11 uses deterministic local
  rules over synthetic records.

## Acceptance Criteria

- Requesters can list only their own feedback requests.
- Requesters can submit feedback once for a requested feedback item.
- Submitted feedback records rating, comment and follow-up preference.
- Duplicate feedback submission is rejected.
- Feedback submissions are recorded on the ticket timeline and audit log.
- Administrators can view global ticket, feedback, reuse and trend metrics.
- RFA managers can view only RFA-scoped analytics.
- Collection managers can view only collection-scoped analytics.
- Unauthorised users cannot access protected analytics dashboards.
- Product reuse analytics count disseminations, accepted existing-product
  offers and feedback per product.
- Trends Analysis Agent produces deterministic insights for request region,
  reuse and requester satisfaction.

## Test Expectations

- Backend API tests cover feedback listing, submission, duplicate rejection,
  admin analytics, team-scoped analytics and unauthorised dashboard access.
- Frontend tests cover feedback submission, feedback permission handling,
  analytics rendering, empty reuse states and API-client calls.
- Existing request, QC, routing and analyst tests continue to pass.
