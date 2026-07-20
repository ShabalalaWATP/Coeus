# Istari AI Agents And Automations

Istari combines deterministic automation with narrowly bounded model-backed
wording. An "agent" does not imply broad autonomy or tool use. Authority comes
only from the workflow service and deterministic policy described here.

> The offline default makes no external calls. Enabling a remote provider is an
> explicit, audited deployment choice and does not grant the provider authority
> to read repositories, call tools or mutate workflow state.

Remote calls reserve shared capacity. Completed calls commit one unit, including
invalid replies that fall back locally; incomplete calls refund it. Metrics omit user IDs.

## Authority matrix

| Automation | Kind | Purpose and inputs | Permitted writes | Must abstain or escalate when | Owner | Version | Egress / rollout |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Customer Chatbot | Model-backed bounded selector | Select the permitted next-question or completion action from extracted intake fields and local safety results | Append application-rendered conversation copy and run records; deterministic extraction may update draft intake | Unsafe input, invalid or oversized output, provider failure, or admission denial | Product owner | Prompt and provider selection recorded per run | Extracted fields only, never raw history; no provider prose; mock default |
| Intake Planner | Deterministic planner with a bounded model preference | Deterministic checks identify contradictions and ambiguity; when the controller is already asking for missing information, admitted model advice may select one supplied missing field | Admitted advice inside the intake run; controller-rendered question only | Safety refusal, blocking contradiction, invalid output, provider failure or no permitted follow-up | Product owner | Prompt, policy and context schema recorded per run | Four purpose-limited fields only; hosted remote egress unavailable; provider cannot discover blocking issues, author copy, declare completeness or change lifecycle |
| RFI Search | Deterministic state-changing | Search the actor-authorised Store corpus using requirement fields and index provenance | Search run, authorised offers and assured search state | Coverage is incomplete, stale or degraded | Intelligence Store owner | Search policy, corpus and embedding versions | Provider allowlist; shadow evaluation before production activation |
| Search Planner | Model-backed bounded advisory | Suggest expansions, entities, date-text interpretations and alternative terminology | Admitted advice and a separate additive retrieval leg; the independent baseline leg and its offers are preserved | Invalid output, provider failure, egress disabled or admission denial | Intelligence Store owner | Prompt, query-admission policy and context schema recorded per run | Minimized intake only, never corpus/results; hosted remote egress disabled by default |
| Similar Request Check | Deterministic advisory and customer decision gate | Compare authorised open-work summaries | Persisted offers; requester endpoints join visible work or continue new tasking; manager endpoints may link related work | Match is hidden, access is lost or retrieval is degraded | Workflow owner | Search/context versions | No hidden match content leaves the access boundary |
| RFA / CM Capability | Deterministic advisory | Assess route signals against intake and capability facts | Review and candidate-team records only | Signals conflict, facts are missing/stale, restrictions or risks exist | RFA / CM managers | Capability catalogue and policy versions | No external egress; active only as advice |
| JIOC Routing | Deterministic state-changing | Decide CM versus RFA from a versioned routing context | Route decision and allowed transition, or manager-review/clarification state | Conflicting signals, stale/missing evidence, restrictions, policy exception or unsafe mode | JIOC Manager | `jioc-routing-policy-v2` plus context schema | No external egress; evaluated release active in local/test, hosted mode explicit |
| JIOC Routing Critic | Deterministic checks plus model-backed shadow advice | Challenge the committed route from structured route, disposition, state, search, capability and capacity facts | Admitted coded critique visible to staff oversight only; hosted processing starts from an identifier-only exact-decision outbox request | Invalid/unavailable output, egress disabled or incomplete critic context | JIOC Manager | Critic prompt, policy and route-context schema recorded per run | Permanently shadow-only; remote egress disabled by default; output cannot propose a route, state, action, disposition or tool call |
| Prioritisation | Deterministic advisory | Order queues from synthetic registry weights | Priority assessment and run record | Required policy inputs are unavailable | JIOC Manager | Prioritisation policy version | No external egress; never changes lifecycle state |
| QC Preflight | Deterministic state-changing gate | Check draft structure, evidence readiness and immutable manifest | Preflight/run/audit records; may block release | Any check fails or the draft changes | QC officer | `qc-preflight-v1` | No external egress; cannot release |
| QC release | Human-only release action | Confirm classification, sources, access and releasability | Published product, dissemination, audit and durable notification intent | Preflight is absent/stale, authority is missing, or version changed | QC officer | Human checklist and release policy | No agent or model can invoke release authority |

### Common authority contract

- Inputs are allowlisted, minimized, versioned and access-filtered before evaluation.
- Model-backed intake receives extracted fields, not raw conversation history;
  other planners receive only their separately documented structured facts.
- Provider output is untrusted: token and byte ceilings, identity-only response
  encoding, a closed action vocabulary and deterministic fallback apply before
  application-owned copy is persisted or displayed.
- Runs record enough provenance to identify provider/model (where applicable),
  prompt, policy and context versions, latency, validation and fallback outcome.
- The evaluated release runs in `active` mode for supported synthetic local/test
  use and decides CM versus RFA. `disabled` invokes no capability agent and refers the
  ticket to `JIOC_REVIEW`; `shadow` records evidence and makes the same referral.
  Any conflict or stale/missing context goes to manual review.
- Humans alone approve final dissemination. Automation cannot expand its own
  permissions, invoke tools, alter policy or bypass object-level authorisation.

### Decision flow and human position

| Stage | Deterministic decision point | Agent freedom | Human position |
| --- | --- | --- | --- |
| Intake | Safety, extraction, contradiction and ambiguity detection, required-field set, close/submit eligibility and the permitted next action | When the deterministic action is already `ask_missing_field`, admitted model advice may prefer one supplied missing field | Requester is in the loop: answers, edits and submits |
| Search | Requester identity, visible corpus, baseline leg, structured filters, ranking threshold, coverage, assurance and workflow outcome | Search Planner may add a bounded supplemental leg but cannot remove or displace baseline offers | Requester is in the loop for offer acceptance/rejection and consent to new tasking |
| JIOC route | Versioned policy validates evidence and actively chooses CM, RFA, clarification or manager review | Routing Critic observes the committed result and may challenge it using closed reason codes | JIOC Managers are on the loop through visibility, metrics, hold/reopen and audited intervention; they enter the loop only on explicit review paths |
| Delivery and release | Assignment, manager approval, QC preflight and release gates | No advisory planner receives these authorities | RFA/CM managers and QC officers remain in the loop at their existing approval gates |

---

## 1. Customer Chatbot Agent

- **Lives in:** `apps/api/src/coeus/services/intake.py` and `intake_standard.py`
- **Classes:** `MockLlmProvider`, `IntakeExtractionService`,
  `RequirementCompletenessService`, `IntakeFieldStandard`

### Purpose

Turn a free-text conversation into a structured, submittable requirement
without ever sounding like a form: chat copy never mentions required fields,
checklists or counts. The chat opens with a greeting, asks one question per
turn, and knows how to end: once the intake is complete the assistant offers
to finish and closes on confirmation, while an early "that's all" gets a
polite explanation that more information is needed, then the next question.
Lifecycle decisions are deterministic (`services/conversation_lifecycle.py`),
never the LLM's. It reads the customer's chat messages only.

### The intake standard

`INTAKE_STANDARD` defines thirteen entries in elicitation order: ten always
required and three urgency entries that apply to critical or high priority.
The completeness gate, workspace checklist and questions all derive from it; see
`docs/specs/intelligence-intake-and-prioritisation.md` for the full list.

On each turn the assistant asks one locally rendered question. Extraction
(`services/intake_extractors.py`) is heuristic, transparent and cue-gated.
Nothing the customer does not provide is invented.

`RequirementCompletenessService` recomputes `missing_information` and
`confidence` (captured / applicable entries) on every message. The workspace
checklist is a direct view of this, and a ticket can only be submitted once
`missing_information` is empty and deterministic contradiction checks pass.

### Intake Planner boundary

Local rules detect invalid or reversed dates, broad geography, vague date
wording and compound operational questions. These findings override model
output and determine the correction strategy. The remote prompt contains only
the operational question, area or region and start/end date, plus the
allowlisted missing-field names. When the deterministic action is already to ask
for missing information, valid advice may choose one of those names. It cannot
create a field, decide completeness or write the requester-facing question.

### Safety

`safety_flags_for` normalises each message and detects instruction override,
privilege escalation and prompt-revelation attempts. Flagged text is recorded
but never extracted or sent to a remote model; every provider path returns fixed
local refusal copy.

### Human control

The customer owns the requirement, can edit any field in the "Edit details
manually" panel, and nothing is submitted until they press Submit.

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

The Search Planner receives bounded intake fields but no corpus, results or
authorisation context. Strictly validated expansions, entities, date-text hints
and alternative terminology form a separate supplemental query. The authorised
baseline query always runs first, and its offers remain ahead of supplemental
offers. Invalid output, provider failure or egress denial produces empty advice,
so baseline retrieval still completes.

### Output

Zero to five `ProductOffer` records with score, reasons, classification,
releasability, region, coverage dates and asset types.

### Human control

The requester accepts or rejects each offer. Acceptance closes the ticket as
`CLOSED_EXISTING_PRODUCT_ACCEPTED`. After assured no-match or rejection, the
active-work check may offer an authorised in-progress request to join. Otherwise
the requester reaches `NEW_TASKING_CONSENT` and decides whether to create new
work. Search cannot consent or route on the requester's behalf.

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

The allowlisted open states from information correction through released-product
review, excluding drafts, holds, cancelled and closed work. The source ticket is
never compared with itself.

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

Both agents use transparent, deterministic route signals and the current
capability catalogue. Their reviews expose eligibility, required clarification,
candidate teams, risks and reasoning. They do not treat a numeric value as
calibrated probability. Conflicting eligibility, negation, missing facts,
restrictions, stale availability or other risk requires clarification or manual
review. Capability reviews are advice and cannot change the lifecycle state.

---

## 5. JIOC Routing Agent and Routing Critic

- **Router:** `services/jioc_routing_agent.py` and `jioc_routing_policy.py`
- **Critic:** `services/routing_critic.py`, `routing_critic_agent.py` and
  `routing_critic_outbox_handler.py`

### Purpose

The active deterministic JIOC Agent decides whether eligible new work needs CM
collection or RFA assessment. Its immutable, versioned context includes search
assurance and offer resolution, active-work discovery, requirement revision,
restrictions, capability catalogue, candidate teams and a fresh capacity
snapshot. It never calls an LLM.

### How it decides

The versioned policy may apply an RFA route to `ANALYST_ASSIGNMENT`, apply a CM
route to `COLLECT_CHOICE`, request clarification in `INFO_REQUIRED`, or abstain to
`JIOC_REVIEW`. Conflicting eligibility, unresolved offers, incomplete search,
stale or missing operational evidence, restrictions and unsafe rollout mode do
not become routine automatic routes. `shadow` records evidence and refers the
case; `disabled` skips the capability evaluation and refers it.

### Critic and human oversight

The shadow-only critic runs after the route is committed. It receives structured
route, disposition, committed-state, search, capability and capacity facts, not
raw ticket identifiers or narrative intake. Output is limited to allowlisted
verdict, challenge, missing-evidence, fact-reference and review-question codes.
Deterministic findings are merged in and cannot be erased by a model.

Local/test runtime records the critique best-effort after routing. Hosted runtime
commits an identifier-only outbox intent atomically with the route; a retry-safe
worker resolves the exact immutable records and writes the critique later. The
critic never delays, reverses or replaces the route. JIOC Managers are on the
loop for routine decisions through queue visibility, metrics and audit. They
enter the loop for explicit review, hold/resume, rerouting intervention and
post-release dispute adjudication.

---

## 6. Prioritisation Agent

- **Lives in:** `apps/api/src/coeus/domain/prioritisation.py` and
  `services/prioritisation.py`

Deterministically scores every intake from synthetic registries (priority
level, region tier with Russia and the Baltic highest, requesting-unit
category, supported-operation type) into a 0..1 score, a P1-P4 tier and
prefixed reason tags. The assessment is stored whenever the intake changes,
recorded as a `prioritisation-agent` run at submission, and orders the
JIOC, team, analyst and QC queues. Managers see the badge and reasons;
customers see only their stated priority; nothing changes state automatically.
The capability agents reuse the tier plus team disciplines, regions and rank
to attach top-3 `candidate_teams` to each review
(`services/capability_recommendation.py`). Weights and details:
`docs/specs/intelligence-intake-and-prioritisation.md` and ADR 0020.

---

## Model provider and selection

The bounded model-backed agents depend on one LLM gateway, not a specific model:

- **Local and test default:** `COEUS_LLM_PROVIDER=mock`. Deterministic, no
  network calls, reproducible in CI.
- **Selectable providers:** Gemini API, OpenAI API, Vertex AI and AWS Bedrock use
  the same bounded gateway and configured model allowlists. Administrators may
  select a provider/model and enter its key in the Admin workspace. Environment
  keys remain authoritative and never select a provider by their presence alone.
- **Graceful degradation:** each agent validates its closed output schema and
  falls back locally on missing credentials, timeout, provider failure, invalid
  output or egress denial. Requester-facing copy is rendered by the application.
- **Future GCP deployment:** the same runtime boundary can point at Google
  managed services without changing the workflow contracts.

Administrators choose the active provider and model from the Admin workspace
(`services/ai_models.py`); each selection raises an audited event. Environment
keys remain authoritative. Admin-entered keys use the configuration-encryption
service and never appear in generic model state or API responses. See the
[User Guide](USER_GUIDE.md#administrator) for the catalogue and tiers.

## Design principles

- **Authority matches proven capability.** Advisory agents cannot mutate workflow;
  active deterministic routing may perform only its allowlisted transitions;
  release, policy and access decisions remain human-only.
- **Need-to-know comes first.** Access policy runs before an agent sees a
  product, so agents cannot leak what a user may not see.
- **Deterministic and auditable.** Local agents are pure functions of their
  inputs, and every human decision they inform is written to the audit log.
- **No tool use in any provider path.** Mock, Gemini, OpenAI, Vertex and Bedrock
  calls cannot act on instructions. Flagged intake is refused locally before any
  external call is made.
