# ADR 0040: Bounded Advisory Planners

## Status

Accepted on 20 July 2026.

## Context

Coeus's deterministic controllers protect workflow and access authority, but
they cannot generate all useful semantic hypotheses. Giving a general LLM direct
control of intake, search or routing would make authorisation and state changes
non-repeatable and vulnerable to prompt injection. Keeping models out of every
step would also discard useful reasoning that can be independently constrained
and evaluated.

## Decision

1. Add separate Intake Planner, Search Planner and Routing Critic capabilities.
2. Treat every model result as untrusted advice admitted through a versioned,
   closed schema with count, length and semantic bounds.
3. Keep the complete deterministic input as the source of truth. Advice may
   reorder a missing-field choice or add a separate recall leg, but cannot
   delete, replace or suppress deterministic constraints or baseline results.
4. Keep authorisation, object visibility, result assurance, workflow transitions
   and route application deterministic.
5. Run the Routing Critic only after decision validation. Hosted routing commits
   an exact, identifier-only request in the same transaction and processes it
   asynchronously. Its output cannot express a route or action and is never
   consumed in the operational route path in this release.
6. Persist normalised plans and standard agent-run provenance, not raw provider
   prompts or replies.
7. Use the existing provider selection, admission, timeout, byte ceiling and
   mock fallback. Hosted Intake egress remains unavailable until ticket
   classification is enforceable. Search and Critic egress are separately
   disabled by default and require provider and data-class release approval.
8. Make provider failure fail local: the owning workflow proceeds with a
   deterministic advisory plan.

## Consequences

- Models get enough freedom to generate useful semantic alternatives while
  their authority remains narrow and testable.
- Each planner can be evaluated and rolled back independently of the controller
  it advises.
- Ticket persistence and staff projections gain additional provenance records.
- Search recall can improve without broadening the authorised corpus or changing
  the conditions for a definitive no-match.
- The Routing Critic can reveal blind spots but cannot correct a route
  automatically until a future, separately approved policy establishes that
  authority.

## Rejected Alternatives

- One orchestration prompt for all stages: it creates excessive context,
  authority and correlated failure.
- Free-form planner prose: it is difficult to validate, evaluate and render
  safely.
- Model-selected authorisation or search assurance: these are policy decisions,
  not semantic suggestions.
- Letting the Routing Critic veto or replace the route: this would make the
  supposed shadow control an undeclared routing authority.
- Storing raw prompts and replies for convenience: this creates unnecessary
  sensitive-data and prompt-injection retention risk.
