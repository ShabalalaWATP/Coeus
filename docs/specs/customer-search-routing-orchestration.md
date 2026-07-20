# Customer Search And Routing Orchestration

## Status

Implemented for the supported synthetic local/test boundary. This specification
supersedes the routing parts of `no-match-consent.md` while retaining its
owner-only and audit controls. Hosted activation and production release remain
subject to the rollout gates below.

## Problem

Submitting a request currently queues RFI search but requires a separate manual
search action. A healthy zero-result search and rejection of the last product can
also route work without one consistent customer decision. Search degradation is
not a first-class workflow state, and active RFI, RFA and collection work is not
offered as a durable alternative to duplicate tasking.

## Customer Contract

Submission starts discovery automatically. The customer receives exactly one of
these outcomes:

1. authorised Intelligence Store products to review;
2. a visible incomplete-search state with a retry action; or
3. after a definitive product no-match, authorised in-progress work to join or a
   decision to create new tasking.

The customer decides whether found products answer the requirement. Retrieval
relevance is never presented as analytic confidence. Rejecting all products does
not itself authorise new work.

## Search Assurance

Every persisted run records separate outcome, assurance and coverage values:

| Outcome | Assurance | Meaning |
| --- | --- | --- |
| `offers` | `assisted` | Customer-reviewed candidates were found. |
| `no_match` | `definitive` | The complete, current and authorised product corpus was evaluated. |
| `incomplete` | `assisted` | Search was stale, partial, unavailable or degraded. |

A definitive no-match requires a ready product index, current corpus identity,
complete extraction and embedding coverage, successful access filtering and no
provider degradation. Metadata or lexical fallback may produce offers, but it
cannot produce a definitive no-match.

## Workflow

```mermaid
stateDiagram-v2
  DRAFT_INTAKE --> RFI_SEARCHING: submit
  RFI_SEARCHING --> RFI_MATCH_OFFERED: product offers
  RFI_SEARCHING --> RFI_SEARCH_INCOMPLETE: coverage not definitive
  RFI_SEARCHING --> NEW_TASKING_CONSENT: definitive product no-match
  RFI_SEARCH_INCOMPLETE --> RFI_MATCH_OFFERED: retry finds products
  RFI_SEARCH_INCOMPLETE --> NEW_TASKING_CONSENT: definitive retry finds none
  RFI_MATCH_OFFERED --> CLOSED_EXISTING_PRODUCT_ACCEPTED: accept product
  RFI_MATCH_OFFERED --> NEW_TASKING_CONSENT: reject all, complete coverage
  RFI_MATCH_OFFERED --> RFI_SEARCH_INCOMPLETE: reject all, partial coverage
  NEW_TASKING_CONSENT --> CLOSED_UNANSWERED: decline new work
  NEW_TASKING_CONSENT --> JIOC_ROUTING_PENDING: authorise new work
```

Before the consent prompt, active-work discovery offers authorised matching RFIs,
RFAs and collection requirements. Joining work creates a durable subscription,
closes the source request as joined and makes the canonical work item the source
of safe customer progress updates. Declining every active-work option proceeds to
the same new-tasking consent prompt.

## JIOC Routing

The JIOC Routing Agent receives the confirmed requirement, product-search run,
product decisions, active-work decisions, safe related-work facts, current
capability catalogue version, candidate teams, availability/workload snapshot and
deterministic policy constraints. The immutable context records its schema and
policy versions, requirement revision, snapshot time and freshness. Its allowed
outputs are `RFA`, `CM`, `CLARIFICATION` and `MANUAL_REVIEW` with structured
reason codes and cited input facts.

Deterministic validation enforces required intake, route eligibility, legal state
transitions and access boundaries. Policy outcomes are explicit eligibility,
ambiguity, insufficient evidence or prohibition, not fixed pseudo-probabilities.
Both routes eligible, negated or contradictory intent, missing/stale facts,
restrictions and policy exceptions route to manual review. The JIOC Manager is on
the loop through an oversight queue, analytics and an audited intervention action,
not a mandatory approval gate.

Routing has three mutually exclusive operational modes:

- `disabled`: deployment kill switch; do not invoke capability agents or persist a route
  decision, then deterministically refer the ticket to `JIOC_REVIEW`;
- `shadow`: persist the context and proposed decision for comparison, then refer
  the ticket to `JIOC_REVIEW` without choosing RFA or CM;
- `active`: apply only a schema-valid, policy-eligible deterministic transition.

The evaluated, version-pinned release is the supported synthetic local/test
default in `active` mode. Hosted deployments must set mode and approval
explicitly. `disabled` takes effect after restart/redeployment; `shadow` is for
evidence-only operation. Routing and QC modules cannot call an LLM adapter.

## Model-backed bounded-selector contract

Customer-chat providers receive only delimited extracted fields and local safety
results, never raw conversation history or workflow repositories. Provider calls
set a maximum output-token budget and bounded timeout; transport requests identity
encoding, rejects encoded responses and enforces a response-byte ceiling. The
provider selects only the allowlisted next-question or completion action, and the
application renders the requester-facing wording. Any other shape or value uses
the deterministic reply and never changes lifecycle behaviour.

Remote runs persist provider, model, prompt version, policy/context versions,
duration and validation/fallback outcome. Raw prompts, credentials and unnecessary
request content are not provenance.

## Collection, Analysis And QC

Work is represented as explicit legs. A collection leg can feed an RFA analysis
leg without overwriting the original route. Each hand-off uses a versioned,
immutable context packet. QC performs a deterministic structural and evidence
readiness preflight; a human QC officer remains the release authority.

## Customer Tracking

Customer status is a safe projection, never the raw operational timeline. It
shows the current public stage, last meaningful update, expected next step and an
ETA range with its basis and confidence. Internal agent prompts, hidden matches,
staff identities, workload details and protected collection information are not
exposed.

## Acceptance Criteria

- Submission automatically attempts discovery and never remains silently queued.
- Product offers are access filtered, grounded and individually accepted or
  rejected by the owner.
- A zero-result degraded search cannot advance to consent or routing.
- All-offer rejection always reaches incomplete search or explicit consent.
- Decline closes as `CLOSED_UNANSWERED`, with the unanswered outcome recorded.
- New-tasking consent is owner-only, CSRF protected, deterministic and audited.
- Active-work joins are durable, idempotent, authorised and customer-trackable.
- JIOC agent output is schema validated and policy checked before transition.
- Conflicting or stale routing evidence can never auto-apply a route.
- Disabled and shadow modes cannot choose RFA or CM or create downstream route
  side effects; both finish at the human JIOC review state.
- Model-backed wording is byte/token bounded and invalid output falls back locally.
- Every remote run is attributable without retaining secrets or raw chat history.
- Human QC is mandatory before release.
- Search evaluation passes the release gates in this specification's test plan.

## Search Release Gates

- access leakage: `0`
- Precision@5: at least `0.95`
- Recall@5: at least `0.95`
- nDCG@5: at least `0.90`
- false definitive no-match rate: at most `0.01`
- false-offer rate: at most `0.02`
- degraded-search detection: `1.00`
- temporal constraint violations: `0`
- citation identity correctness: `1.00`
- offered passage support: at least `0.95`

## Rollout

Ship automatic discovery, active-work offers and JIOC agent decisions behind
independent controls. Provider and embedding-model activation remains blocked by
the release-gate evaluation and an explicit deployment allowlist. The labelled
conflict, negation, stale-context and authority suites now approve the pinned
`active` routing release; use `shadow` for comparison and `disabled` for rollback
on any access, assurance or state-integrity breach. Deterministic QC preflight is
a mandatory safety control, not an optional rollout path.

Before real or sensitive data, deployment additionally requires approved data
classification, DLP/redaction and egress policy; provider/model/region allowlists;
retention rules; a representative human-labelled evaluation corpus; calibration,
drift and rollback evidence; and a recorded decision on any proposal to enrich
provider context beyond extracted fields.
