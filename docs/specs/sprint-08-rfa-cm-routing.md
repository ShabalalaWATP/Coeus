# Sprint 8 Spec: RFA And CM Routing

## Goal

Add the first controlled routing layer after RFI search cannot satisfy a request.
Sprint 8 must run deterministic RFA and CM capability checks, present manager
queues, require human approval before analyst assignment, support clarification
requests and record project-plan updates.

## In Scope

- RFA capability output with capability, confidence, clarifications, work
  packages, team suggestion, effort, risks and reasoning.
- CM capability output with capability, confidence, clarifications, collection
  route, source suggestions, effort, risks and reasoning.
- RFA-first routing when assessment can satisfy the request.
- CM fallback when RFA cannot satisfy and collection can.
- Human manager approval, rejection and clarification request actions.
- Override approval with required reason and audit event.
- Ticket-level project-plan update records.
- RFA and CM manager queue frontend pages.

## Out Of Scope

- Analyst task execution and work package ownership. That starts in Sprint 9.
- Persistent PostgreSQL route-review tables. Sprint 8 keeps local-first records on
  the ticket aggregate.
- Real LLM-backed route recommendations.
- Real collection tasking systems or external source integrations.

## Acceptance Criteria

- Route checks run only for tickets in `ROUTE_ASSESSMENT`.
- Both RFA and CM capability reviews are stored for every route check run.
- If both routes can satisfy, RFA is preferred.
- If RFA cannot satisfy and CM can satisfy, the ticket enters
  `CM_MANAGER_REVIEW`.
- If neither route can satisfy, the ticket enters `INFO_REQUIRED` with focused
  clarification requirements.
- Approval transitions to `ANALYST_ASSIGNMENT` and appends a project-plan update.
- Clarification and rejection require a reason and create audit events.
- Override approval requires an override reason and creates a `manager_override`
  audit event.
- Customers cannot access manager queues or manager actions.
