# ADR 0020: Deterministic Priority Ranking And Team Recommendation

## Status

Accepted

## Context

Ticket queues were ordered by creation time only; the customer's stated
priority influenced nothing. The intake now captures ranking signals
(requesting unit, supported operation, disciplines) and the platform needs an
internal ordering that reflects region, operation type and requesting-unit
precedence, plus a better way to suggest which capability team should take a
request. ADR 0009 anticipated replacing the deterministic keyword matcher
without changing route handlers or frontend contracts.

## Decision

- A pure function (`domain/prioritisation.py`) scores each intake from
  synthetic registries: priority level 0.35, region tier 0.25, requesting-unit
  category 0.20 and supported-operation type 0.20, producing a 0..1 score,
  a P1-P4 tier and prefixed reason tags in the established scoring idiom.
- The assessment is stored on the ticket at every intake mutation and recorded
  as a `prioritisation-agent` run at submission; queues sort by
  `(-score, created_at)` with on-the-fly scoring for legacy tickets. It is
  manager-facing only.
- The capability catalogue gains disciplines, regions and rank per team, and a
  weighted scorer (`services/capability_recommendation.py`: relevance 0.4,
  region 0.3, rank 0.2, priority fit 0.1) returns top-3 candidates with
  reasons on each RFA/CM review. Suggested-team and triage-fallback semantics
  are unchanged, and managers still approve every route.
- No LLM involvement anywhere in ranking or recommendation: both are
  deterministic, explainable and unit-testable.

## Consequences

- Queue order is now explainable from reason tags and audited via agent runs,
  but customer-provided text (region, unit, operation) influences internal
  ordering; the threat model records this and the manager-only visibility.
- Legacy tickets persisted before the change decode with a `None` assessment
  and are scored on read, so no migration is needed.
- Registry weights are demo data; a production deployment would replace them
  with governed configuration rather than code constants.
