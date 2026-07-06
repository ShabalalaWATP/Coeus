# Istari AI Agents

Istari is an AI-first tasking system. A small set of focused agents sit behind
the workflow and do the repetitive reasoning, while a person always makes the
decision that changes state. This document describes each agent precisely: what
triggers it, what it reads, how it decides, what it returns, and where the human
stays in control.

> All agents are deterministic mocks in local and test environments
> (`COEUS_LLM_PROVIDER=mock`). They do not call an external model, they never
> execute user instructions, and every input is treated as synthetic. In a
> deployed environment the same interfaces are backed by Gemma on Vertex AI (see
> [Model provider and selection](#model-provider-and-selection)).

## Agents at a glance

| Agent | Stage | Trigger | Output | Human decision |
| --- | --- | --- | --- | --- |
| Intake assistant | Describe the need | Customer chat message | Extracted requirement, completeness, safety flags | Customer confirms and submits |
| RFI Search Agent | Search existing intelligence | Ticket submitted | Ranked existing-product offers | Customer accepts or rejects an offer |
| RFA Capability Agent | Route review | Manager runs capability checks | Assessment-route feasibility review | RFA manager approves, rejects or queries |
| CM Capability Agent | Route review | Manager runs capability checks | Collection-route feasibility review | CM manager approves, rejects or queries |
| Route recommendation | Route review | Both capability reviews complete | Recommended route + reasoning | Manager may follow or override with a reason |

The stages map one-to-one onto the customer-facing
[request journey](USER_GUIDE.md#the-request-journey).

---

## 1. Intake assistant

- **Lives in:** `apps/api/src/coeus/services/intake.py`
- **Classes:** `MockLlmProvider`, `IntakeExtractionService`, `RequirementCompletenessService`

### Purpose

Turn a free-text conversation into a structured, submittable requirement without
making the customer fill in a long form.

### What it reads

The customer's chat messages only. It never reads other tickets, products or
user data.

### What it extracts

The assistant works towards seven required fields:

1. `title`
2. `description`
3. `operational_question`
4. `area_or_region`
5. `priority`
6. `required_output_format`
7. `customer_success_criteria`

Extraction is heuristic and transparent: for example a phrase after "titled" or
the first six words becomes the title, a sentence ending in "?" becomes the
operational question, and keywords such as "critical/high/medium/low" set the
priority. Anything the customer does not provide is left blank rather than
invented.

### Completeness and confidence

`RequirementCompletenessService` recomputes, on every message:

- `missing_information` — the required fields still blank.
- `confidence` — `fields_present / 7`, rounded to two decimals.

The workspace checklist ("N of 7 captured") is a direct view of this. A ticket
can only be submitted once `missing_information` is empty.

### Safety

`safety_flags_for` scans each message against a fixed list of prompt-injection
markers (for example "ignore previous instructions", "make me admin", "reveal
hidden prompt"). If any is present the assistant returns a fixed refusal message
and flags `prompt_injection_attempt`; it never acts on the instruction, because
the mock provider has no tools and no privileges to act with in the first place.

### Output

An updated `IntakeDetails` record plus an assistant reply that either asks for
the top missing fields or confirms the requirement is ready to submit.

### Human control

The customer owns the requirement. They can also edit any field directly in the
"Edit details manually" panel, and nothing is submitted until they press Submit.

---

## 2. RFI Search Agent

- **Lives in:** `apps/api/src/coeus/services/rfi_ranking.py` and `services/rfi_search.py`
- **Entry point:** `rank_rfi_hits(hits, intake)`

### Purpose

Answer "does an existing product already satisfy this?" before any new tasking
is raised, so effort is not duplicated. This is the "search before you task"
principle.

### What it reads

Only products the requesting user is allowed to see. The candidate set is
produced by the store's access policy first (ACG membership, clearance and
product status), so the agent can never rank, score or reveal a product the user
has no need-to-know for.

### How it scores

For each candidate the query text (title, operational question, region, known
context, output format, success criteria) is compared to the product:

| Signal | Weight | Basis |
| --- | --- | --- |
| Full-text overlap | 0.45 | Query tokens found in the product's text |
| Semantic overlap | 0.40 | Cosine-style token overlap normalised by length |
| Metadata match | up to 0.24 | Region match (+0.16), output-format/type match (+0.08) |

Scores are capped at 1.0. A product is only offered when its score is at or above
the **offer threshold of 0.25**, and at most **five** offers are returned,
highest score first. Each offer carries its `match_reasons` (for example
`full-text:baltic`, `semantic:assessment`, `metadata:region`) so the customer can
see why it was suggested.

### Output

Zero to five `ProductOffer` records with score, reasons, classification,
releasability, region, coverage dates and asset types.

### Human control

The customer accepts or rejects each offer. Accepting an offer closes the ticket
as satisfied by an existing product (`CLOSED_EXISTING_PRODUCT_ACCEPTED`);
rejecting all of them sends the ticket on to route assessment. The agent never
closes a ticket by itself.

---

## 3 & 4. Capability Agents (RFA and CM)

- **Live in:** `apps/api/src/coeus/services/routing_agents.py`
- **Classes:** `RfaCapabilityAgent`, `CmCapabilityAgent`

### Purpose

Advise the route managers on whether the request is better served by an
assessment-led route (RFA, Request for Assessment) or a collection-led route (CM,
Collection Management), and surface the clarifications and risks a manager should
weigh.

### What they read

The ticket's intake text: title, description, operational question, region,
required output format, known context and success criteria.

### How they decide

Both agents tokenise the intake and look for domain signals:

- **Assessment signal:** terms such as *assessment, assess, brief, report,
  estimate, analysis*.
- **Collection signal:** terms such as *collection, sensor, imagery, source,
  monitor, surveillance*.
- **Unsupported markers:** terms such as *mars, unknown, tbd, unbounded* raise a
  clarification instead of a confident answer.

From those signals each agent produces:

- `can_satisfy` — the RFA agent says yes when there is an assessment signal, no
  outstanding clarifications, and the request is not purely collection-led; the
  CM agent says yes when there is a collection signal and no clarifications.
- `confidence` — 0.86 when it can satisfy, 0.48 when a signal exists but is
  unconfirmed, 0.34 with no signal, and 0.28 when clarifications are outstanding.
- `required_clarifications` — carried over from missing intake plus any raised by
  unsupported markers or a critical priority with no deadline.
- `suggested_work_packages` (RFA) or `suggested_collection_sources` (CM).
- `estimated_effort` — "1-2 days" for critical/high priority, otherwise
  "3-5 days".
- `risks` and a plain-language `reasoning_summary`.

### Output

An `RfaCapabilityReview` and a `CmCapabilityReview`, both rendered on the manager
queue as agent-badged cards.

### Human control

Both reviews set `manager_review_required = True`. They are advice only; a
manager must approve, reject or request clarification.

---

## 5. Route recommendation

- **Lives in:** `apps/api/src/coeus/services/routing_records.py` (`recommend_route`)
- **Orchestrated by:** `RoutingService.run_reviews` in `services/routing.py`

### Purpose

Combine the two capability reviews into a single recommended route and move the
ticket into the correct manager queue.

### How it decides

The recommendation prefers the route whose capability agent can satisfy the
request with the higher confidence, falling back to collection management when the
request is collection-led. The resulting state is either `RFA_MANAGER_REVIEW` or
`CM_MANAGER_REVIEW`.

### Human control

The recommendation is a default, not a decision. A manager can approve the
recommended route, or approve the other route by supplying a written
**override reason**, which is recorded as a `manager_override` audit event. Every
approval, rejection and clarification is written to the audit log.

---

## Model provider and selection

The agents depend on an LLM provider interface, not on a specific model:

- **Local and test:** `COEUS_LLM_PROVIDER=mock`. Deterministic, no network calls,
  reproducible in CI.
- **Deployed:** `gemma_vertex`, backed by Gemma on Vertex AI. Configuration lives
  in `apps/api/src/coeus/integrations/gcp/gemma.py`.

Administrators choose which Gemini/Gemma model the agents should use from the
Admin workspace. The catalogue, tiers and the audit of who last changed the model
are described in the [User Guide](USER_GUIDE.md#administrator) and implemented in
`apps/api/src/coeus/services/ai_models.py`. The selection records the active
model and raises an `ai_model_changed` audit event; the provider stays `mock`
locally, so the choice documents intent for deployed environments without
changing local behaviour.

## Design principles

- **A person makes every state change.** Agents extract, rank and advise; they
  never approve, release or close.
- **Need-to-know comes first.** Access policy runs before an agent sees a
  product, so agents cannot leak what a user may not see.
- **Deterministic and auditable.** Local agents are pure functions of their
  inputs, and every human decision they inform is written to the audit log.
- **No tool use in the mock.** The local provider cannot act, so prompt injection
  has nothing to act on; it is flagged and refused.
