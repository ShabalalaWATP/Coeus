# Istari AI Agents

Istari is an AI-first tasking system. A small set of focused agents sit behind
the workflow and do the repetitive reasoning, while a person always makes the
decision that changes state. This document describes each agent precisely: what
triggers it, what it reads, how it decides, what it returns, and where the human
stays in control.

> Agents are deterministic mocks by default in local and test environments
> (`COEUS_LLM_PROVIDER=mock`). They do not call an external model, they never
> execute user instructions, and every input is treated as synthetic. Admins can
> configure a Gemini API key locally for the chatbot response provider without
> requiring Google Cloud hosting. The configured provider setting is
> authoritative: an API key supplied through the environment never switches the
> provider by itself.

## Agents at a glance

| Agent                  | Stage                        | Trigger                                 | Output                                            | Human decision                                  |
| ---------------------- | ---------------------------- | --------------------------------------- | ------------------------------------------------- | ----------------------------------------------- |
| Customer Chatbot Agent | Describe the need            | Customer chat message                   | Extracted requirement, completeness, safety flags | Customer confirms and submits                   |
| RFI Search Agent       | Search existing intelligence | Ticket submitted                        | Ranked offers or a no-match decision point        | Customer accepts, rejects or confirms tasking   |
| Similar Request Check  | Search existing intelligence | Submitted request reaches open workflow | Similar open tickets and reasons                  | Customer may join or continue; manager may link |
| RFA Capability Agent   | Route review                 | Manager runs capability checks          | Assessment-route feasibility review               | RFA manager approves, rejects or queries        |
| CM Capability Agent    | Route review                 | Manager runs capability checks          | Collection-route feasibility review               | CM manager approves, rejects or queries         |
| Orchestrator Agent     | Route review                 | RFI search plus RFA and CM reviews      | Recommended route and reasoning                   | Manager may follow or override with a reason    |

The stages map one-to-one onto the customer-facing
[request journey](USER_GUIDE.md#the-request-journey).

---

## 1. Customer Chatbot Agent

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

Extraction is heuristic and transparent: for example a phrase after "titled"
becomes the title (or the first six words, when the message reads like a
requirement statement), a sentence ending in "?" becomes the operational
question, and keywords such as "critical/high/medium/low" set the priority.
Anything the customer does not provide is left blank rather than invented: no
operational question or success criteria is ever synthesised on the customer's
behalf.

### Completeness and confidence

`RequirementCompletenessService` recomputes, on every message:

- `missing_information` — the required fields still blank.
- `confidence` — `fields_present / 7`, rounded to two decimals.

The workspace checklist ("N of 7 captured") is a direct view of this. A ticket
can only be submitted once `missing_information` is empty.

### Safety

`safety_flags_for` normalises each message first (casefolded, zero-width
characters stripped, whitespace collapsed) and then scans it against families
of prompt-injection markers: instruction-override phrasing and its common
synonyms, privilege-escalation requests such as "make me admin", and attempts
to reveal hidden or system prompts. Simple bypasses such as unusual casing,
doubled spaces, newlines between words or zero-width characters do not evade
the scan. If a message is flagged the assistant returns a fixed refusal on
every provider path, the flagged text is never sent to an external model, and
intake extraction is skipped entirely so injected text cannot land in any
requirement field. The user message, the flags and the refusal are still
recorded on the ticket.

### Output

An updated `IntakeDetails` record plus an assistant reply that either asks for
the top missing fields or confirms the requirement is ready to submit.

### Human control

The customer owns the requirement. They can also edit any field directly in the
"Edit details manually" panel, and nothing is submitted until they press Submit.

---

## 2. RFI Search Agent

- **Lives in:** `apps/api/src/coeus/services/rfi_ranking.py`,
  `services/rfi_search.py` and `services/embeddings.py`
- **Entry point:** `RfiSearchService.run(ticket_id, actor)`

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

The agent builds query text from title, operational question, region, known
context, output format and success criteria, then runs two retrieval legs over
the access-filtered product set:

| Signal          | Basis                                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Lexical rank    | PostgreSQL full-text rank when relational search is available, with the deterministic token scorer as the local fallback |
| Semantic rank   | Cosine similarity against 384-dimension product embeddings from the configured embedding provider                        |
| Semantic labels | Controlled labels derived from product and request language                                                              |
| Metadata        | Region and output-format or product-type overlap                                                                         |

Lexical and semantic ranks are fused with Reciprocal Rank Fusion (`k = 60`).
Metadata and semantic-label signals are deterministic tie-break bonuses on the
fused score. Scores are normalised to 0..1, and a product is offered only when it
is at or above the calibrated hybrid threshold. At most five offers are returned,
highest score first. Each offer carries `match_reasons`, including legacy
reasons such as `metadata:region` plus hybrid reasons such as `lexical-rank:2`,
`vector-similarity:0.83` and `retrieval:lexical-only`.

`COEUS_EMBEDDING_PROVIDER` is authoritative. The default `mock` provider is
deterministic and offline. Optional `local` and `gemini_api` providers degrade to
lexical-only retrieval if unavailable, and Gemini is never called unless the
operator explicitly selects the Gemini embedding provider.

### Output

Zero to five `ProductOffer` records with score, reasons, classification,
releasability, region, coverage dates and asset types.

### Human control

The customer accepts or rejects each offer. Accepting an offer closes the ticket
as satisfied by an existing product (`CLOSED_EXISTING_PRODUCT_ACCEPTED`);
rejecting all offered products sends the ticket on to route assessment. If no
product matches at all, the ticket stops in `RFI_NO_MATCH` and asks the owner to
confirm new tasking or cancel. The agent never closes or tasks a ticket by
itself.

---

## 2a. Similar Request Check

- **Lives in:** `apps/api/src/coeus/services/similar_requests.py` and
  `services/similar_request_scoring.py`
- **Entry points:** `/api/v1/similar-requests/tickets/{ticket_id}` and
  `/api/v1/similar-requests/routing/{ticket_id}`

### Purpose

Warn humans when another open request appears to cover the same work, so teams
can consolidate early without blocking a customer's submitted request.

### What it reads

Open tickets from `RFI_SEARCHING` through `MANAGER_RELEASE`, including the
`RFI_NO_MATCH` consent state. Draft,
`INFO_REQUIRED`, cancelled and closed tickets are excluded, and the source ticket
is never compared with itself.

### How it scores

The check reuses the hybrid retrieval approach over each ticket's intake text:
lexical rank plus embedding similarity are fused with Reciprocal Rank Fusion
(`k = 60`), then small region and output-format bonuses are applied. Customer
notices use a higher threshold than manager panels because customer disclosure is
more sensitive.

### Human control and visibility

Customers only see reference, title, score and reasons for matching tickets that
the existing ticket visibility policy already lets them read. Hidden matches
produce only a neutral notice. Customers can join a visible match as a viewer or
continue their own request. RFA and Collection managers see matching open
requests in the routing queue and can link them as related, which writes both
ticket timelines and the audit log.

---

## 3 & 4. Capability Agents (RFA and CM)

- **Live in:** `apps/api/src/coeus/services/routing_agents.py`
- **Classes:** `RfaCapabilityAgent`, `CmCapabilityAgent`

### Purpose

Advise RFA and Collection managers on whether the request is better served by an
assessment-led route (RFA, Request for Assessment) or a collection-led route (CM,
Collection Management), and surface the clarifications and risks a manager should
weigh.

### What they read

The ticket's intake text: title, description, operational question, region,
required output format, known context and success criteria.

### How they decide

Both agents tokenise the intake on alphanumeric runs (so punctuation such as
"assessment?" still matches) with simple plural folding, and look for domain
signals:

- **Assessment signal:** terms such as _assessment, assess, brief, report,
  estimate, analysis_.
- **Collection signal:** terms such as _collection, sensor, imagery, source,
  monitor, surveillance_.
- **Unsupported markers:** terms such as _mars, tbd, unbounded_ raise a
  clarification instead of a confident answer.

From those signals each agent produces:

- `can_satisfy` — the RFA agent says yes when there is an assessment signal, no
  outstanding clarifications, and the request is not purely collection-led; the
  CM agent says yes only when a genuine collection term is present and there
  are no clarifications. A collection-team keyword match on its own is treated
  as an unconfirmed signal, not a confident answer.
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

## 5. Orchestrator Agent

- **Lives in:** `apps/api/src/coeus/services/routing_records.py` (`recommend_route`)
- **Orchestrated by:** `RoutingService.run_reviews` in `services/routing.py`

### Purpose

Combine RFI search results and the two capability reviews into a single
recommended route. If existing intelligence or an RFA route can satisfy the
request, collection is avoided. If the intelligence is missing and collection
signals are present, the orchestrator recommends the Collection manager queue.

### How it decides

The recommendation prefers RFA when the assessment route can satisfy the
request, falls back to collection management when collection is needed, and asks
for clarification when neither path has enough information. The resulting state
is `RFA_MANAGER_REVIEW`, `CM_MANAGER_REVIEW` or `INFO_REQUIRED`.

When clarification is required, the orchestrator hands the questions back
through the customer chatbot. The ticket receives a normal assistant message
containing the actual questions, plus a `customer_clarification_sent` timeline
event, so the customer does not need to inspect manager-only route metadata.

### Human control

The orchestrator is a recommendation source, not a route manager. A human RFA or
Collection manager can approve the recommended route, or approve the other route
by supplying a written
**override reason**, which is recorded as a `manager_override` audit event. Every
approval, rejection and clarification is written to the audit log.

---

## Model provider and selection

The agents depend on an LLM provider interface, not on a specific model:

- **Local and test default:** `COEUS_LLM_PROVIDER=mock`. Deterministic, no
  network calls, reproducible in CI.
- **Local optional:** admins can enter a Gemini API key and select the active
  model from the Admin workspace. Entering a key through the Admin workspace is
  an explicit opt-in to the Gemini provider; a key present only in the
  environment never changes the configured provider. The key is held by the
  running API process, never returned to the browser and not persisted to
  generic app state.
- **Graceful degradation:** if the Gemini API is unavailable, times out or is
  selected without a key, the chatbot falls back to the deterministic mock
  reply. The customer's message is always saved and the chat turn never fails
  because the external provider did.
- **Future GCP deployment:** the same runtime boundary can point at Google
  managed services without changing the workflow contracts.

Administrators choose which Gemini model the chatbot provider should use from the
Admin workspace. The catalogue, tiers and the audit of who last changed the
model are described in the [User Guide](USER_GUIDE.md#administrator) and
implemented in `apps/api/src/coeus/services/ai_models.py`. The selection records
the active model and raises an `ai_model_changed` audit event. Persisted
provider credentials should be supplied through environment configuration or a
secret manager, not through the admin UI runtime key field.

## Design principles

- **A person makes every state change.** Agents extract, rank and advise; they
  never approve, release or close.
- **Need-to-know comes first.** Access policy runs before an agent sees a
  product, so agents cannot leak what a user may not see.
- **Deterministic and auditable.** Local agents are pure functions of their
  inputs, and every human decision they inform is written to the audit log.
- **No tool use in any provider path.** Neither the mock nor the Gemini path can
  act on instructions, and flagged messages are refused locally on both paths
  before any external call is made.
