# ADR 0045: Bounded Current-Answer Intake Interpretation

## Status

Accepted.

## Context

Istari's deterministic intake extractor is predictable and safe, but a value
outside its known aliases can leave a required field unresolved. The existing
planner sees only previously extracted fields, so adding an API key does not
help it understand that answer. Repeating the same field question does not
explain the failure and creates a conversational loop.

Sending full chat history to a model would widen privacy, prompt-injection and
retention exposure. Allowing model-authored values to mutate intake would also
move workflow authority outside the application.

## Decision

Use a deterministic-first interpretation boundary:

1. Apply local extraction and clarification handling first.
2. Only when the active target field remains unresolved, allow the configured
   Intake Planner to receive the bounded current customer answer, target field
   and current calendar date. Do not send prior messages or unrelated fields.
3. Limit model interpretation to priority and time period. Free-text intake
   remains deterministic and local.
4. Require exact-key JSON with the target field, an evidence substring copied
   from the current answer, optional closed normalisation and an abstention flag.
5. Admit a priority suggestion only from the application enum and dates only as
   a valid ordered ISO range. Show the suggestion in application-owned copy and
   persist it only after an explicit customer confirmation. Reject extra fields,
   invented evidence, invalid types and malformed output. Treat valid abstention
   as a successful provider response followed by deterministic fallback.
6. Keep the model tool-free and non-authoritative. Deterministic completeness,
   contradiction, lifecycle, authorisation and submission controllers remain
   final.
7. Reserve provider capacity before execution, share the provider circuit
   breaker and record only safe provenance and hashes. An interpretation call
   replaces remote planning for that turn so one message causes at most one
   external call.
8. Derive retry and pending-confirmation state from persisted assistant
   messages. After the initial field question, respond with an example rather
   than the same question. After another unresolved answer, direct the customer
   to Edit details without asking again.

Hosted Intake Planner egress remains disabled. Enabling it requires a separate
approved classification, provider, retention and regional release. Local use
continues to require synthetic data.

## Consequences

- A configured model can propose normalisation for natural priority and date
  wording that local rules do not understand, without gaining state or workflow
  authority. The customer remains the authority for accepting that proposal.
- The model receives one raw current answer on the exceptional fallback path,
  but never the conversation history. Operators must still approve provider
  handling before enabling hosted egress.
- Invalid, abstaining or unavailable model output leaves intake unchanged and
  produces actionable deterministic guidance.
- Transcript-derived retry state avoids a persistence migration and naturally
  resets when the customer or manual editor satisfies the field.
