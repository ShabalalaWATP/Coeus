# ADR 0036: Customer Search Assurance And Agent Routing

## Status

Accepted, 2026-07-18.

## Context

Coeus already has useful Gemini embeddings, hybrid retrieval, pgvector, document
chunking and grounded citations. The weakness is orchestration and assurance, not
the basic retrieval approach. A zero-result response is currently inferred from
the absence of offers even when semantic retrieval or index coverage is degraded.
The customer decision is also split between no-match and offer-rejection paths.

JIOC routing is currently a human review step supported by deterministic agents.
The intended operating model needs an agent to make routine routing decisions,
with deterministic policy enforcement and a JIOC Manager able to observe and
intervene without approving every request.

## Decision

1. Retain the current retrieval stack and evaluate providers against a fixed,
   versioned corpus before changing the embedding model.
2. Persist outcome, assurance, coverage and index provenance for every discovery
   run. Only complete, current, authorised coverage can yield a definitive
   no-match.
3. Run discovery automatically after submission, with an idempotent outbox retry
   for interrupted work.
4. Use one owner-only new-tasking consent state after product and active-work
   options have been resolved.
5. Persist active-work offers and subscriptions rather than treating a join as a
   navigation-only action.
6. Introduce a schema-constrained JIOC Routing Agent whose result is validated by
   deterministic policy. Exceptions go to human review.
7. Keep the JIOC Manager on the loop with an audited intervention capability.
8. Keep final dissemination under human QC authority. QC agent output is advisory
   and must not release a product.
9. Permit production search providers and embedding models only after the fixed
   evaluation corpus passes every release gate and the deployment is explicitly
   allowlisted.

## Consequences

- Existing embeddings and grounded evidence remain valuable and do not need a
  premature provider migration.
- More workflow states and durable records are required, with legacy state decode
  support and versioned codec compatibility for existing persistence snapshots.
- Customer status requires a separate safe projection.
- Agent prompts and model outputs become versioned operational artefacts subject
  to evaluation, audit and rollback.
- Search latency moves into the submission journey, so the UI must show progress
  and an honest incomplete state when bounded work cannot finish.

## Rejected Alternatives

- Treating every zero-result run as definitive was rejected because provider and
  index failures can masquerade as no-match.
- Routing immediately after the last rejected offer was rejected because product
  rejection is not consent to create new tasking.
- Making the JIOC Manager approve every route was rejected because it keeps the
  manager in the loop and prevents routine automation.
- Letting an LLM change ticket state directly was rejected because access,
  eligibility and transition rules must remain deterministic.
