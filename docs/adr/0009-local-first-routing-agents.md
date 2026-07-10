# ADR 0009: Local-First RFA And CM Routing Agents

## Status

Accepted.

## Context

Sprint 8 requires RFA and CM capability agents, RFA-first routing, CM fallback,
manager queues and human approval. The repository must remain public-safe and
local-first, so route decisions cannot depend on external LLMs, collection
systems, real products or cloud credentials.

## Decision

Implement deterministic local capability agents behind service boundaries:

- `RfaCapabilityAgent` evaluates assessment suitability from structured intake.
- `CmCapabilityAgent` evaluates collection suitability from structured intake.
- `RoutingService` runs both reviews, stores structured outputs on the ticket
  aggregate and chooses the route.
- Manager approvals, rejections, clarifications and overrides are explicit
  service actions with audit events.
- Workflow plan updates are ticket-level records used to explain routing and
  assignment state changes.

## Consequences

- Sprint 8 remains reproducible in CI and local development.
- Route decisions are explainable and covered by behaviour tests.
- Future LLM-backed or database-backed route agents can replace the deterministic
  adapters without changing route handlers or frontend contracts.
- The local heuristic is intentionally conservative and does not claim real
  operational capability.
