# ADR 0036: Customer Search Assurance And Agent Routing

## Status

Accepted, 2026-07-18.

## Context

Coeus already has useful Gemini embeddings, hybrid retrieval, pgvector, document
chunking and grounded citations. The weakness is orchestration and assurance, not
the basic retrieval approach. A zero-result response is currently inferred from
the absence of offers even when semantic retrieval or index coverage is degraded.
The customer decision is also split between no-match and offer-rejection paths.

JIOC routing may automate routine state changes, but that authority must be
narrower than the capability producing the recommendation. A JIOC Manager must
be able to observe and intervene without becoming a mandatory approval step for
every proven-safe route.

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
10. Treat routing rollout as three explicit modes: `disabled` invokes no
    capability agent and deterministically refers the ticket for human JIOC
    review; `shadow` records a decision for comparison and makes the same human
    referral; `active` permits only allowlisted deterministic route transitions.
    `disabled` is the safe default; deployment configuration must opt in to the
    other modes.
11. Do not represent fixed rule outputs as calibrated probability. Routing policy
    uses explicit eligibility, ambiguity, insufficient-evidence and prohibited
    outcomes. Numeric confidence may inform humans only after calibration against
    a versioned labelled corpus.
12. A routing context includes requirement revision, search/related-work evidence,
    capability catalogue version, candidate-team capability and availability,
    snapshot time, freshness and policy/context versions. Missing, stale,
    conflicting or restricted context always selects manual review.
13. Model-backed intake components have bounded selector authority only. They
    choose an allowlisted question/completion action, while the application
    renders requester-facing copy. Untrusted provider output is bounded at
    generation and identity-only transport, validated before use and replaced by
    a deterministic fallback on failure. Raw conversation history is not provider
    context.
14. Persist provider/model and prompt/policy/context provenance, duration and
    validation/fallback outcome for remote runs, without secrets or unnecessary
    raw content.
15. Dead-lettered workflow work is an operator-visible failure state. It requires
    metrics, alerting and an authorised, reason-required, audited, idempotent replay
    that retains the original event identity.
16. Defer full model governance, DLP and large-scale evaluation infrastructure
    while the application is synthetic, but make them mandatory gates before real
    or sensitive data and before production model-backed decision support.

## Consequences

- Existing embeddings and grounded evidence remain valuable and do not need a
  premature provider migration.
- More workflow states and durable records are required, with legacy state decode
  support and versioned codec compatibility for existing persistence snapshots.
- Customer status requires a separate safe projection.
- Agent prompts and model outputs become versioned operational artefacts subject
  to evaluation, audit and rollback.
- The authority inventory in `docs/AI_AGENTS.md` is reviewed with every new agent,
  policy version or permitted write. Provider adapters cannot import workflow or
  persistence services, and deterministic decision modules cannot import outbound
  provider integrations.
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
