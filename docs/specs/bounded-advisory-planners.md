# Bounded Advisory Planners

## Status

Approved implementation specification.

## Problem

Coeus has deliberately deterministic controllers for intake progression,
authorised retrieval and JIOC routing. Those controls protect authority, but the
system currently underuses model reasoning where it can improve the quality of
the evidence presented to those controllers. In particular, it does not retain a
structured account of intake contradictions, broader search terminology or a
second opinion on an applied routing decision.

## Decision And Authority Model

Three narrowly scoped advisory agents are introduced. They may analyse and
propose, but they never own an external or state-changing decision.

| Agent | May propose | Deterministic authority remains with |
| --- | --- | --- |
| Intake Planner | contradictions, ambiguities, a follow-up strategy and the most useful missing field | conversation lifecycle, permitted next action and application-owned requester wording |
| Search Planner | query expansions, entities, date interpretations and alternative terminology | requester authorisation, access filtering, retrieval limits, temporal metadata filters, ranking assurance and workflow outcome |
| Routing Critic | a support/challenge verdict, bounded reason codes, cited facts and missing evidence | JIOC routing policy, transition validation and the active JIOC Routing Agent |

Provider output is untrusted data. Every remote result must pass a strict,
bounded schema and semantic allowlist. An absent, invalid, unavailable or
rate-limited provider produces a deterministic local plan and does not block the
owning workflow.

## Shared Planner Contract

Each plan records:

- a unique plan identifier and ticket identifier;
- agent, prompt, policy and context-schema versions;
- execution kind, provider and model when applicable;
- validation and fallback outcomes;
- hashes of the bounded input and admitted output;
- timestamps and only the normalised, admitted advisory fields.

No plan stores credentials, raw prompts, raw model replies or full conversation
history. Text values are length and count bounded. Unknown keys, unknown enums,
control characters and malformed values invalidate the remote result. Provider
admission, timeout, output-token and response-byte controls apply to every remote
planner call.

## Intake Planner

The input is the currently extracted `IntakeDetails`, its deterministic missing
fields and local safety flags. Raw chat history is excluded. The planner returns:

- zero or more contradiction observations, each identifying only allowlisted
  intake fields;
- zero or more ambiguity observations, each identifying only allowlisted fields;
- ordered follow-up strategies from an allowlist;
- one suggested next field, which must be in the controller's current missing
field set, or `null`;
- an abstention flag.

The controller selects the permitted action. Safety refusal and conversation
close rules run before planner advice. A valid suggestion may reorder only the
existing deterministic missing-field queue. It cannot mark a requirement
complete, remove a required field, emit arbitrary requester prose or change
ticket state. The controller independently detects impossible or reversed date
windows and blocks submission until they are corrected. It renders fixed,
application-owned questions for proven contradictions and supported ambiguity
signals. A requester may explicitly accept a softer ambiguity and finish, but
cannot override a proven contradiction.

## Search Planner

The input is the submitted extracted requirement. The plan contains bounded,
normalised query expansions, entities, date interpretations and alternative
terms. The query controller always runs the complete deterministic base query as
an independent retrieval leg. It may run a second additive leg with admitted
unique terms, then union the results while preserving every baseline offer.

Planner output affects query recall only. The original `IntakeDetails` remains
the sole source for structured region and time filtering. Product eligibility is
resolved for the requester before ranking, evidence is projected only for
visible offers, and search coverage and definitive no-match assurance are
calculated without model authority. Hybrid and grounded retrieval receive the
same query within each leg. A supplemental failure degrades assurance and
planner advice can neither suppress a baseline match nor create a definitive
no-match. Requester-visible metrics contain the base query only; admitted hints
remain staff-only advice.

## Routing Critic

The critic runs after the JIOC deterministic policy has produced and validated a
routing decision. It receives only the immutable routing context and admitted
decision facts. It returns a bounded support, challenge, insufficient-evidence
or unavailable verdict with allowlisted challenge codes, missing-evidence codes,
cited fact identifiers and application-owned review-question codes. Its schema
deliberately has no recommended route, target state, action, disposition or tool
field.

The critic is permanently shadow-only in this release. Its record is appended
for staff oversight and evaluation, but its output is not read by the state
transition, route side effects, customer messages or downstream hand-offs. A
hosted route transaction atomically commits an identifier-only critique request
to the durable outbox and returns immediately. The worker resolves the exact
decision/context/reviews, runs the critic and persists idempotently. Provider,
worker or critique-storage failure can therefore never fail or delay a valid
deterministic routing decision. Local/test mode may record the deterministic
mock critique inline to keep development feedback immediate.

## Human In And On The Loop

- The requester is in the loop for intake answers, product acceptance and new
  tasking consent.
- The JIOC Routing Agent is active when the deployment's separately controlled
  routing mode and release gates permit it.
- JIOC Managers are on the loop through visibility of the deterministic decision
  and shadow critique, analytics and audited intervention. They are in the loop
  only for explicit clarification, manual-review or intervention paths.
- RFA and Collection Managers remain in the loop for their existing work
  approval and assignment responsibilities. The planners do not alter them.
- Human QC remains the product release authority.

## Acceptance Criteria

- All three planner records are immutable, versioned and attributable.
- Local/mock operation produces deterministic plans without provider access.
- Remote calls use provider admission and bounded structured output.
- Invalid or unavailable provider output falls back without blocking workflow.
- Intake advice cannot remove required fields, close a conversation or author
  requester-facing prose.
- Search planning cannot expand the visible corpus, weaken structured metadata
  filters or create a definitive no-match.
- Routing criticism cannot change a decision, target state or side effect.
- Staff projections expose admitted advice without exposing prompts, secrets or
  unauthorised content; customer projections do not expose internal critique.
- Labelled tests cover valid, invalid, adversarial, unavailable and abstaining
  provider cases, plus authority-invariance properties.
- Backend and frontend line and branch coverage remain at least 95 per cent.

## Rollout And Evaluation

`mock` is the safe fallback. Hosted Intake Planner egress is unavailable until
ticket classification is enforceable. Search Planner and Routing Critic egress
is disabled independently by default. Enabling either requires its per-agent flag,
an approved provider and the current `synthetic` data-class release. Before any
real or sensitive data, add a separately reviewed classification, redaction,
provider, model, region, retention and egress release. Routing prompts expose
derived facts and counts, not raw ticket, product, team or review identifiers.
Hosted shadow or active JIOC routing also requires relational PostgreSQL persistence
so every critic request is committed atomically with its exact route decision.

Release evidence must separately measure intake issue precision, useful-field
selection, search Recall@5 and false-offer rate, and critic disagreement quality.
No metric may be improved by weakening access leakage, temporal violations,
false definitive no-match or state-integrity gates.
